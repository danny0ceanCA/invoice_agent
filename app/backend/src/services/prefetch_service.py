"""Background prefetching of likely follow-up analytics reports using Celery."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

import structlog

from tasks.worker import celery

LOGGER = structlog.get_logger(__name__)


def _derive_prefetch_queries(
    normalized_intent: dict[str, Any] | None,
    last_rows: list[dict[str, Any]] | None,
    router_decision: Mapping[str, Any] | None,
) -> list[str]:
    """Derive a small set of likely follow-up natural-language queries.

    Minimal v1 behavior:
    - If the user asked for student_monthly_spend (cost) for a student,
      prefetch the hours query, provider breakdown, service code breakdown,
      and latest invoice details for the same student when available.
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

        # ---------------------------
        # Option A Prefetch Additions
        # ---------------------------

        # Provider breakdown
        queries.append(f"provider breakdown for {student_name}")

        # Service code breakdown
        queries.append(f"service code breakdown for {student_name}")

        # Invoice details for latest month (if last_rows available)
        if isinstance(last_rows, list) and last_rows:
            # Expect last_rows to have "service_month"
            try:
                months = [
                    row.get("service_month")
                    for row in last_rows
                    if isinstance(row.get("service_month"), str)
                ]
                if months:
                    # Use the most recent month (last in order)
                    latest_month = months[-1]
                    queries.append(
                        f"invoice details for {student_name} in {latest_month}"
                    )
            except Exception as exc:  # defensive
                LOGGER.warning(
                    "prefetch_latest_month_failed",
                    error=str(exc),
                )

    return queries


def enqueue_prefetch_jobs(
    *,
    normalized_intent: dict[str, Any] | None,
    last_rows: list[dict[str, Any]] | None,
    router_decision: Mapping[str, Any] | None,
    district_key: str,
    user_id: int | None,
) -> None:
    """Enqueue background jobs to prefetch likely follow-up reports.

    Best-effort only; failures are logged and never affect the main response.
    """

    try:
        queries = _derive_prefetch_queries(normalized_intent, last_rows, router_decision)
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
