"""Service layer functions for administrative user management."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.backend.src.models import User

ALLOWED_ROLES: set[str] = {"vendor", "district", "admin"}


def _get_user_or_404(session: Session, user_id: int) -> User:
    user = session.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def list_users(session: Session) -> list[User]:
    """Return all users ordered by creation time descending."""

    return (
        session.query(User)
        .options(selectinload(User.vendor), selectinload(User.district))
        .order_by(User.created_at.desc())
        .all()
    )


def list_pending_users(session: Session) -> list[User]:
    """Return users that have not been approved yet."""

    return (
        session.query(User)
        .options(selectinload(User.vendor), selectinload(User.district))
        .filter(User.is_approved.is_(False), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .all()
    )


def approve_user(session: Session, user_id: int) -> User:
    """Mark a user as approved and active."""

    user = _get_user_or_404(session, user_id)
    user.is_approved = True
    user.is_active = True
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def decline_user(session: Session, user_id: int) -> User:
    """Decline a pending user by deactivating their account."""

    user = _get_user_or_404(session, user_id)
    user.is_active = False
    user.is_approved = False
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user_role(session: Session, user_id: int, role: str) -> User:
    """Update a user's role after validating the value."""

    normalized_role = (role or "").strip().lower()
    if normalized_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    user = _get_user_or_404(session, user_id)
    user.role = normalized_role
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def deactivate_user(session: Session, user_id: int) -> User:
    """Soft deactivate a user account."""

    user = _get_user_or_404(session, user_id)
    user.is_active = False
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


__all__ = [
    "list_users",
    "list_pending_users",
    "approve_user",
    "decline_user",
    "update_user_role",
    "deactivate_user",
]

