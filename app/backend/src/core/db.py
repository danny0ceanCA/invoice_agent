"""Database session management."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_ENGINE = create_engine(get_settings().database_url, future=True)
_SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, class_=Session)


@contextmanager
def get_db() -> Session:
    """Yield a database session."""

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
