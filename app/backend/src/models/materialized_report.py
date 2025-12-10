"""Materialized analytics report storage."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, JSON, Index

from app.backend.src.db.base import Base


class MaterializedReport(Base):
    """Persisted analytics reports for reuse across sessions and cache flushes."""

    __tablename__ = "materialized_reports"

    id: int = Column(Integer, primary_key=True, autoincrement=True)

    # Tenant scoping
    district_key: str = Column(String(64), nullable=False, index=True)

    # Cache key (same SHA256 used for Redis analytics cache)
    cache_key: str = Column(String(128), nullable=False, index=True)

    # High-level semantics
    report_kind: str | None = Column(String(128), nullable=True, index=True)
    primary_entity: str | None = Column(String(255), nullable=True, index=True)

    # Serialized AgentResponse (text, html, rows, etc.)
    payload: dict[str, Any] = Column(JSON, nullable=False)

    created_at: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    last_accessed_at: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


Index(
    "ix_materialized_reports_district_kind_entity",
    MaterializedReport.district_key,
    MaterializedReport.report_kind,
    MaterializedReport.primary_entity,
)

__all__ = ["MaterializedReport"]
