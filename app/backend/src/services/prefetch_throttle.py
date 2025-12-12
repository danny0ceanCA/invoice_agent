"""Prefetch throttling utilities."""

from __future__ import annotations

import time
from typing import Mapping

import structlog
from redis import Redis

from tasks.worker import celery

LOGGER = structlog.get_logger(__name__)


def _count_small_queue(tasks_mapping: dict | None) -> int:
    """Return the count of tasks routed to the small queue."""

    if not tasks_mapping:
        return 0

    count = 0
    for tasks in tasks_mapping.values():
        for task in tasks or []:
            delivery_info = task.get("delivery_info") or {}
            routing_key = delivery_info.get("routing_key")
            if routing_key == "small":
                count += 1
    return count


def should_throttle_prefetch(
    *,
    settings,
    district_key: str,
    normalized_intent: dict | None,
    router_decision: Mapping | None,
    num_predicted_queries: int,
) -> tuple[bool, str]:
    """Return whether prefetch should be throttled and why."""

    if not settings.prefetch_enabled:
        return True, "disabled"

    # Queue depth
    try:
        inspector = celery.control.inspect()
        if inspector:
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            queue_depth = _count_small_queue(active) + _count_small_queue(reserved)
            if queue_depth > settings.prefetch_max_queue:
                return True, "queue_depth"
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_queue_inspect_failed", error=str(exc))

    # Minimum interval
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        last_ts_raw = client.get(f"prefetch:last_ts:{district_key}")
        if last_ts_raw is not None:
            try:
                last_ts = float(last_ts_raw)
            except (TypeError, ValueError):
                last_ts = None
            if last_ts is not None:
                if time.time() - last_ts < settings.prefetch_min_interval_sec:
                    return True, "min_interval"
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_interval_check_failed", error=str(exc))

    # Redis key count safety valve
    try:
        client = Redis.from_url(settings.redis_url)
        try:
            info = client.info() or {}
            db0 = info.get("db0") or {}
            keys_count = db0.get("keys")
        except Exception:
            keys_count = client.dbsize()
        if keys_count is not None and keys_count > settings.prefetch_max_redis_keys:
            return True, "redis_keys"
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_key_count_failed", error=str(exc))

    # Complexity guardrails
    try:
        if settings.prefetch_skip_expensive:
            mode = None
            plan_kind = None
            if isinstance(router_decision, Mapping):
                mode = router_decision.get("mode")
                plan_kind = router_decision.get("plan_kind") or router_decision.get("kind")

            if isinstance(normalized_intent, dict):
                intent_name = normalized_intent.get("intent")
            else:
                intent_name = None

            if plan_kind == "invoice_details" or mode == "invoice_details":
                return True, "expensive"

            if isinstance(intent_name, str) and (
                intent_name.startswith("district_")
                or intent_name.startswith("comparison")
            ):
                return True, "expensive"
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_complexity_check_failed", error=str(exc))

    return False, ""
