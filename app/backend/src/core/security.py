"""Security helpers for Auth0 integration."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.backend.src.db import get_session_dependency
from app.backend.src.models import User


def get_current_user(
    user_id: int = Header(alias="X-User-Id"),
    session: Session = Depends(get_session_dependency),
) -> User:
    """Resolve the authenticated user from the request headers."""

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    return user


__all__ = ["get_current_user"]
