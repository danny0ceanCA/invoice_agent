"""Celery tasks for analytics prefetching."""

from __future__ import annotations

from typing import Any

import structlog

from .worker import celery

LOGGER = structlog.get_logger(__name__)


@celery.task(name="tasks.small.prefetch_analytics")
def prefetch_analytics(query: str, context: dict[str, Any] | None = None, queue_name: str | None = None) -> None:
    """Background Celery task to prefetch analytics reports using the REAL agent."""

    if context is None:
        context = {}

    try:
        # Correct import: call the REAL district analytics pipeline
        from app.backend.src.agents.district_analytics_agent import run_analytics_agent
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_import_failed", error=str(exc))
        return

    try:
        run_analytics_agent(
            query=query,
            context=context,
            district_key=context.get("district_key"),
        )
        LOGGER.info(
            "prefetch_analytics_completed",
            query=query,
            district_key=context.get("district_key"),
            session_id=context.get("session_id"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "prefetch_analytics_failed",
            query=query,
            district_key=context.get("district_key"),
            session_id=context.get("session_id"),
            error=str(exc),
        )
