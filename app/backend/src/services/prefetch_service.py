"""Background prefetching of likely follow-up analytics reports using Celery."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

import structlog

from tasks.worker import celery

LOGGER = structlog.get_logger(__name__)


def _derive_prefetch_queries(
    normalized_intent: dict[str, Any] | None,
    router_decision: Mapping[str, Any] | None,
) -> list[str]:
    """Derive a small set of likely follow-up natural-language queries.

    Minimal v1 behavior:
    - If the user asked for student_monthly_spend (cost) for a student,
      prefetch the hours query for the same student.
    """

    if not isinstance(normalized_intent, dict):
        return []

    intent = normalized_intent.get("intent")
    entities = normalized_intent.get("entities") or {}
    student_name = entities.get("student_name")

    if not isinstance(student_name, str) or not student_name.strip():
        return []

    queries: list[str] = []

    # If the current query is student_monthly_spend, prefetch student_monthly_hours.
    if intent == "student_monthly_spend":
        queries.append(f"i want to see the hours for {student_name}")

    # Future: add provider breakdown, year summary, etc.

    return queries


def enqueue_prefetch_jobs(
    *,
    normalized_intent: dict[str, Any] | None,
    router_decision: Mapping[str, Any] | None,
    district_key: str,
    user_id: int | None,
) -> None:
    """Enqueue background jobs to prefetch likely follow-up reports.

    Best-effort only; failures are logged and never affect the main response.
    """

    try:
        queries = _derive_prefetch_queries(normalized_intent, router_decision)
        if not queries:
            return

        for q in queries:
            session_id = f"prefetch-{uuid.uuid4()}"

            celery.send_task(
                "tasks.small.prefetch_analytics",
                args=[
                    q,
                    {
                        "district_key": district_key,
                        "session_id": session_id,
                        "user_id": user_id,
                    },
                ],
                kwargs={"queue_name": "small"},
            )

        LOGGER.info(
            "prefetch_jobs_enqueued",
            district_key=district_key,
            num_queries=len(queries),
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("enqueue_prefetch_jobs_failed", error=str(exc))
