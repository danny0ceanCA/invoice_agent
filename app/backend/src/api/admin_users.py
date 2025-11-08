"""Administrative endpoints for managing user accounts."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from app.backend.src.core.security import require_role
from app.backend.src.db import get_session_dependency
from app.backend.src.models import User
from app.backend.src.services import admin_users as admin_user_service


class UserOut(BaseModel):
    """Serialized representation of a user for admin responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: str | None
    is_approved: bool
    is_active: bool
    vendor_id: int | None
    vendor_company_name: str | None
    district_id: int | None
    district_company_name: str | None


class RoleUpdate(BaseModel):
    """Payload for updating a user's role."""

    role: str


class UserActionResponse(BaseModel):
    """Response returned after an administrative action on a user."""

    message: str
    user: UserOut


router = APIRouter(prefix="/admin", tags=["Admin Users"])

require_admin_role = require_role(["admin"], allow_admin=True)

logger = logging.getLogger(__name__)


@router.get(
    "/users",
    response_model=list[UserOut],
    dependencies=[Depends(require_admin_role)],
)
def list_users(
    session: Annotated[Session, Depends(get_session_dependency)],
) -> list[User]:
    """Return all users in the system."""

    return admin_user_service.list_users(session)


@router.get(
    "/users/pending",
    response_model=list[UserOut],
    dependencies=[Depends(require_admin_role)],
)
def list_pending_users(
    session: Annotated[Session, Depends(get_session_dependency)],
) -> list[User]:
    """Return all users awaiting approval."""

    return admin_user_service.list_pending_users(session)


@router.patch(
    "/users/{user_id}/approve",
    response_model=UserActionResponse,
    dependencies=[Depends(require_admin_role)],
)
def approve_user(
    user_id: int,
    session: Annotated[Session, Depends(get_session_dependency)],
    admin_user: Annotated[User, Depends(require_admin_role)],
) -> dict[str, User]:
    """Approve a pending user."""

    user = admin_user_service.approve_user(session, user_id)
    logger.info(
        "Admin %s approved %s",
        admin_user.email,
        user.email,
    )
    return {
        "message": "User approved successfully",
        "user": user,
    }


@router.delete(
    "/users/{user_id}/decline",
    response_model=UserActionResponse,
    dependencies=[Depends(require_admin_role)],
)
def decline_user(
    user_id: int,
    session: Annotated[Session, Depends(get_session_dependency)],
    admin_user: Annotated[User, Depends(require_admin_role)],
) -> dict[str, User]:
    """Decline a pending user and deactivate their account."""

    user = admin_user_service.decline_user(session, user_id)
    logger.info(
        "Admin %s declined %s",
        admin_user.email,
        user.email,
    )
    return {
        "message": "User declined successfully",
        "user": user,
    }


@router.patch(
    "/users/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_admin_role)],
)
def update_role(
    user_id: int,
    payload: RoleUpdate,
    session: Annotated[Session, Depends(get_session_dependency)],
) -> User:
    """Update the role for a user."""

    try:
        return admin_user_service.update_user_role(session, user_id, payload.role)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - unexpected
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update user role",
        ) from exc


@router.patch(
    "/users/{user_id}/deactivate",
    response_model=UserOut,
    dependencies=[Depends(require_admin_role)],
)
def deactivate_user(
    user_id: int,
    session: Annotated[Session, Depends(get_session_dependency)],
) -> User:
    """Deactivate a user."""

    return admin_user_service.deactivate_user(session, user_id)


__all__ = [
    "router",
    "RoleUpdate",
    "UserOut",
    "UserActionResponse",
    "require_admin_role",
]

