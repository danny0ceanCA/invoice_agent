"""Database session management utilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from ..models.base import Base

from .session import SessionLocal, engine as _engine

# Safe session manager for FastAPI + SQLAlchemy
# Prevents premature close() during active transactions


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager yielding a SQLAlchemy session."""

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        if db.is_active:
            db.close()


def get_session_dependency() -> Iterator[Session]:
    """FastAPI dependency wrapping :func:`get_session`."""

    with get_session() as session:
        yield session


def get_engine():
    """Return the configured SQLAlchemy engine."""

    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope for background workers."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if session.is_active:
            session.close()


__all__ = [
    "Base",
    "get_engine",
    "get_session",
    "get_session_dependency",
    "session_scope",
]
