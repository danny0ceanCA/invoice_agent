"""SQLAlchemy engine and session factory configuration."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.src.core.config import get_settings

_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

__all__ = ["engine", "SessionLocal"]
