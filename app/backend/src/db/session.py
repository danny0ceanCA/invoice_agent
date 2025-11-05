"""SQLAlchemy engine and session factory configuration."""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from app.backend.src.core.config import get_settings

LOGGER = structlog.get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _normalize_database_url(raw_url: str) -> URL:
    """Return an absolute :class:`~sqlalchemy.engine.URL` for SQLite databases."""

    url = make_url(raw_url)
    if not url.drivername.startswith("sqlite"):
        return url

    database = url.database or ""
    if database in {"", ":memory:"}:
        return url

    db_path = Path(database)
    if db_path.is_absolute():
        resolved = db_path
    else:
        resolved = PROJECT_ROOT / db_path

    resolved = resolved.resolve()
    if resolved != db_path:
        LOGGER.info(
            "database_path_normalized",
            original=str(db_path),
            resolved=str(resolved),
        )

    return url.set(database=str(resolved))


_settings = get_settings()
_database_url = _normalize_database_url(_settings.database_url)
engine = create_engine(
    _database_url,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

LOGGER.info("database_engine_initialized", url=str(_database_url))

__all__ = ["engine", "SessionLocal"]
