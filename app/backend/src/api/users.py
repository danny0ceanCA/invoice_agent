"""User management endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.backend.src.core.security import get_current_user
from ..db import get_session_dependency
from app.backend.src.models import User, Vendor

router = APIRouter(prefix="/users", tags=["users"])

RoleOption = Literal["vendor", "district"]


class RoleSelectionPayload(BaseModel):
    """Payload describing the role selected during onboarding."""

    role: RoleOption


@router.post("/set-role")
def set_user_role(
    payload: RoleSelectionPayload,
    session: Session = Depends(get_session_dependency),
    current_user: User = Depends(get_current_user),
) -> dict[str, object | None]:
    """Assign the onboarding role for the authenticated user."""

    if current_user.role == "admin":
        return {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "vendor_id": current_user.vendor_id,
            "district_id": getattr(current_user, "district_id", None),
            "auth0_sub": current_user.auth0_sub,
            "needs_role_selection": False,
        }

    if current_user.role and current_user.role != payload.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role has already been assigned",
        )

    if current_user.role != payload.role:
        current_user.role = payload.role

    if payload.role == "vendor":
        if getattr(current_user, "district_id", None) is not None:
            current_user.district_id = None
        if current_user.vendor_id is None:
            vendor = Vendor(
                company_name=_generate_company_name(current_user, "Vendor"),
                contact_name=current_user.name,
                contact_email=current_user.email,
            )
            session.add(vendor)
            session.flush()
            current_user.vendor_id = vendor.id
    elif payload.role == "district":
        if current_user.vendor_id is not None:
            current_user.vendor_id = None
        current_user.district_id = None

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "vendor_id": current_user.vendor_id,
        "district_id": current_user.active_district_id,
        "auth0_sub": current_user.auth0_sub,
        "needs_role_selection": False,
    }


def _generate_company_name(user: User, suffix: str) -> str:
    """Return a default organization name for onboarding."""

    base = (user.name or "").strip()
    if not base and user.email:
        base = user.email.split("@")[0]
    if not base:
        base = "Organization"
    return f"{base} {suffix} {user.id}"[:255]
