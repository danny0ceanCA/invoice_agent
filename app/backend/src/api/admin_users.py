"""Administrative endpoints for managing user accounts."""

from __future__ import annotations

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


class RoleUpdate(BaseModel):
    """Payload for updating a user's role."""

    role: str


router = APIRouter(prefix="/admin", tags=["Admin Users"])

require_admin_role = require_role(["admin"], allow_admin=True)


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


@router.post(
    "/users/{user_id}/approve",
    response_model=UserOut,
    dependencies=[Depends(require_admin_role)],
)
def approve_user(
    user_id: int,
    session: Annotated[Session, Depends(get_session_dependency)],
) -> User:
    """Approve a pending user."""

    return admin_user_service.approve_user(session, user_id)


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


__all__ = ["router", "RoleUpdate", "UserOut", "require_admin_role"]

