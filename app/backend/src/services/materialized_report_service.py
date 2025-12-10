"""Helpers for persisting materialized analytics reports."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.backend.src.models.materialized_report import MaterializedReport

LOGGER = structlog.get_logger(__name__)


def _extract_report_kind(
    normalized_intent: dict[str, Any] | None, router_decision: dict[str, Any] | None
) -> str | None:
    """Best-effort extraction of a semantic report kind."""
    if isinstance(router_decision, dict):
        mode = router_decision.get("mode")
        if isinstance(mode, str) and mode:
            return mode

    if isinstance(normalized_intent, dict):
        intent = normalized_intent.get("intent")
        if isinstance(intent, str) and intent:
            return intent

    return None


def _extract_primary_entity(router_decision: dict[str, Any] | None) -> str | None:
    if not isinstance(router_decision, dict):
        return None
    primary_entities = router_decision.get("primary_entities") or []
    if isinstance(primary_entities, list) and primary_entities:
        first = primary_entities[0]
        if isinstance(first, str):
            return first
    return None


def persist_materialized_report(
    *,
    engine: Engine,
    district_key: str,
    cache_key: str,
    normalized_intent: dict[str, Any] | None,
    router_decision: dict[str, Any] | None,
    agent_response: dict[str, Any],
) -> None:
    """Persist a cached analytics report to Postgres.

    This is a best-effort operation; failures are logged but do not affect the response.
    """

    try:
        with Session(engine) as session:
            report = MaterializedReport(
                district_key=district_key,
                cache_key=cache_key,
                report_kind=_extract_report_kind(normalized_intent, router_decision),
                primary_entity=_extract_primary_entity(router_decision),
                payload=agent_response,
            )
            session.add(report)
            session.commit()
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning(
            "persist_materialized_report_failed",
            district_key=district_key,
            cache_key=cache_key,
            error=str(exc),
        )
