"""Database session management utilities."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app.backend.src.core.config import get_settings

_settings = get_settings()
_engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)
_SessionFactory = scoped_session(
    sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)
)


def get_engine():
    """Return the configured SQLAlchemy engine."""

    return _engine


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a SQLAlchemy session."""

    session = _SessionFactory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope for background workers."""

    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_engine", "get_session", "session_scope"]
