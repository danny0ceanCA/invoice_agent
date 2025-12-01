from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, List


@dataclass
class RouterDecision:
    mode: str  # e.g. "student_monthly", "invoice_details", "provider_breakdown"
    primary_entity_type: str | None
    primary_entities: List[str]
    time_window: str | None
    month_names: List[str]
    metrics: List[str]
    needs_invoice_details: bool
    needs_provider_breakdown: bool
    notes: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def route_sql(
    *,
    user_query: str,
    sql_plan: dict | None,
    entities: dict | None,
    normalized_intent: dict | None,
    multi_turn_state: dict | None,
) -> RouterDecision:
    """
    Routes a semantic SQL plan into a high-level RouterDecision for logic_model.
    Does not generate SQL. Does not access database. Pure semantic routing.
    """

    # 1) Infer default values
    plan = sql_plan or {}
    ents = entities or {}
    intent = normalized_intent or {}
    mt = multi_turn_state or {}

    primary_type = plan.get("primary_entity_type")
    primary_entities = (
        plan.get("primary_entities") or ents.get(primary_type + "s", []) if primary_type else []
    )

    time_window = plan.get("time_window") or intent.get("time_period", {}).get("relative")
    month_names = plan.get("month_names") or intent.get("time_period", {}).get("month", [])
    metrics = plan.get("metrics") or []

    # Flags
    q_lower = user_query.lower()
    needs_invoice_details = any(
        kw in q_lower
        for kw in [
            "invoice details",
            "line items",
            "line item",
            "breakdown",
            "drill",
            "show me the details",
        ]
    )

    needs_provider_breakdown = any(
        kw in q_lower for kw in ["provider", "clinician", "hours by provider", "who provided"]
    )

    # Modes
    if needs_invoice_details:
        mode = "invoice_details"
    elif needs_provider_breakdown:
        if primary_type == "student":
            mode = "student_provider_breakdown"
        else:
            mode = "provider_breakdown"
    elif primary_type == "student":
        mode = "student_monthly"
    elif primary_type == "vendor":
        mode = "vendor_monthly"
    else:
        mode = plan.get("kind") or "district_summary"

    # Multi-turn: preserve active filters when plan doesn't override
    if mt.get("active_topic") and mode != "invoice_details":
        active = mt["active_topic"]
        if active.get("type") == "student" and not primary_entities:
            primary_entities = [active.get("value")]

    if mt.get("last_month") and not month_names:
        month_names = [mt["last_month"]]

    return RouterDecision(
        mode=mode,
        primary_entity_type=primary_type,
        primary_entities=primary_entities or [],
        time_window=time_window,
        month_names=month_names if isinstance(month_names, list) else [],
        metrics=metrics if isinstance(metrics, list) else [],
        needs_invoice_details=needs_invoice_details,
        needs_provider_breakdown=needs_provider_breakdown,
        notes=[],
    )
