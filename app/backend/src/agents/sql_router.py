from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import Any, List

import structlog
from openai import OpenAI


LOGGER = structlog.get_logger(__name__)


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
    date_range: dict | None

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
    date_range = plan.get("date_range") if isinstance(plan.get("date_range"), dict) else None
    metrics = plan.get("metrics") or []

    # Flags
    q_lower = user_query.lower()
    top_invoices_intent = any(
        kw in q_lower
        for kw in [
            "highest invoices",
            "most expensive invoices",
            "top invoices",
            "biggest invoices",
            "highest cost invoices",
        ]
    ) or ("top" in q_lower and "invoice" in q_lower)

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
    ) and not top_invoices_intent

    needs_provider_breakdown = any(
        kw in q_lower for kw in ["provider", "clinician", "hours by provider", "who provided"]
    ) and not top_invoices_intent

    # Modes
    if top_invoices_intent or plan.get("kind") == "top_invoices":
        mode = "top_invoices"
        primary_type = None
        primary_entities = []
        needs_invoice_details = False
        needs_provider_breakdown = False
    elif needs_invoice_details:
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

    # Fallback provider logic for student queries with month detection
    q_lower = user_query.lower()
    mentions_provider = any(
        t in q_lower for t in [
            "provider", "providers", "clinician", "clinicians"
        ]
    )
    mentions_hours_or_cost = any(
        t in q_lower for t in [
            "hours", "cost", "spend", "total"
        ]
    )

    # Pull month from any available source
    month_from_state = None
    if isinstance(mt, dict):
        month_from_state = mt.get("last_month")

    has_month = (
        (month_names and len(month_names) > 0) or
        bool(month_from_state)
    )

    # FINAL FALLBACK LOGIC
    if (
        mode not in ["invoice_details", "top_invoices"]
        and primary_type == "student"
        and mentions_provider
        and mentions_hours_or_cost
    ):
        if time_window in ["this_school_year", "school_year", "ytd"] and not has_month:
            mode = "student_provider_year"
        else:
            mode = "student_provider_breakdown"

        needs_provider_breakdown = True

        LOGGER.debug(
            "router_mode_override",
            mode=mode,
            reason="student provider fallback with month detection",
            month=month_names,
            month_from_state=month_from_state,
        )

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
        date_range=date_range,
    )


def build_sql_router_system_prompt() -> str:
    """System prompt for AI-driven routing of semantic SQL plans."""

    return """
You are the SQL routing model for the district analytics agent.

Your task is to map a semantic SQL plan, normalized intent, entities, and the
multi-turn conversation state into a RouterDecision JSON object. Do NOT write
SQL and do NOT describe logic—only emit the routing JSON.

RouterDecision schema (all keys required):
- mode: string. One of: district_summary, student_monthly, vendor_monthly,
  invoice_details, student_provider_breakdown, provider_breakdown, top_invoices.
- primary_entity_type: string|null. Usually "student" or "vendor".
- primary_entities: array of strings.
- time_window: string|null. e.g., "last_month", "this_school_year".
- month_names: array of strings. e.g., ["August"].
- metrics: array of strings for requested measures (e.g., cost, hours).
- needs_invoice_details: boolean. True when the user wants invoice/line-item
  detail or says "drill", "line items", etc.
- needs_provider_breakdown: boolean. True when the user wants results broken
  down by provider/clinician.
- notes: array of strings for any clarifications or routing notes.

Routing rules (strict):
- If the user asks for "highest invoices", "most expensive invoices", "top invoices", "biggest invoices", "highest cost invoices", or "top N invoices" → mode=top_invoices with no invoice details or provider breakdown.
- If the user wants invoice details or line-item drilldowns → mode=invoice_details.
- If provider breakdown is requested and the primary type is student →
  mode=student_provider_breakdown, else provider_breakdown.
- If primary entity is a student → mode=student_monthly.
- If primary entity is a vendor → mode=vendor_monthly.
- Otherwise default to district_summary.

NEW MODE RULE — student_provider_year:
- If intent/entities indicate a single student,
- AND the user asks for providers/clinicians and hours,
- AND the time period is this_school_year,
- AND NO explicit month is mentioned,
Then mode MUST be 'student_provider_year'.

Multi-turn context:
- Preserve the active_topic and last_month fields from the multi_turn_state when
  the current plan does not override them.

Output:
- Return ONLY a single JSON object that matches the RouterDecision schema.
- Never include SQL, prose, or explanations.
"""


def _coerce_router_decision(payload: dict[str, Any], fallback: RouterDecision) -> RouterDecision:
    if not isinstance(payload, dict):
        return fallback

    def _as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int, float))]
        if isinstance(value, (str, int, float)):
            return [str(value)]
        return []

    mode = payload.get("mode") or fallback.mode
    primary_entity_type = payload.get("primary_entity_type") or fallback.primary_entity_type
    primary_entities = _as_list(payload.get("primary_entities")) or fallback.primary_entities
    time_window = payload.get("time_window") or fallback.time_window
    month_names = _as_list(payload.get("month_names")) or fallback.month_names
    metrics = _as_list(payload.get("metrics")) or fallback.metrics
    needs_invoice_details = bool(payload.get("needs_invoice_details", fallback.needs_invoice_details))
    needs_provider_breakdown = bool(payload.get("needs_provider_breakdown", fallback.needs_provider_breakdown))
    notes = _as_list(payload.get("notes")) or []
    date_range = payload.get("date_range") if isinstance(payload.get("date_range"), dict) else fallback.date_range

    if not mode:
        return fallback

    return RouterDecision(
        mode=str(mode),
        primary_entity_type=str(primary_entity_type) if primary_entity_type else None,
        primary_entities=primary_entities,
        time_window=str(time_window) if time_window else None,
        month_names=month_names,
        metrics=metrics,
        needs_invoice_details=needs_invoice_details,
        needs_provider_breakdown=needs_provider_breakdown,
        notes=notes,
        date_range=date_range if isinstance(date_range, dict) else None,
    )


def run_sql_router_model(
    *,
    user_query: str,
    sql_plan: dict | None,
    entities: dict | None,
    normalized_intent: dict | None,
    multi_turn_state: dict | None,
    client: OpenAI,
    model: str,
    system_prompt: str,
    temperature: float,
) -> RouterDecision:
    """Execute the AI router model with a deterministic fallback."""

    fallback_decision = route_sql(
        user_query=user_query,
        sql_plan=sql_plan,
        entities=entities,
        normalized_intent=normalized_intent,
        multi_turn_state=multi_turn_state,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": user_query,
                    "sql_plan": sql_plan or {},
                    "entities": entities or {},
                    "normalized_intent": normalized_intent or {},
                    "multi_turn_state": multi_turn_state or {},
                    "baseline_router_decision": fallback_decision.to_dict(),
                }
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        assistant_content = response.choices[0].message.content if response.choices else None
        parsed = json.loads(assistant_content or "{}")
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("router_model_failed", error=str(exc))
        return fallback_decision

    router_decision = _coerce_router_decision(parsed, fallback_decision)

    q_lower = (user_query or "").lower()
    mentions_provider = any(
        kw in q_lower for kw in ["provider", "providers", "clinician", "clinicians", "therapist", "therapists"]
    )
    mentions_hours = "hour" in q_lower or "time" in q_lower or "service hour" in q_lower

    time_window = router_decision.time_window or (
        (normalized_intent or {}).get("time_period", {}) if isinstance(normalized_intent, dict) else {}
    )
    if isinstance(time_window, dict):
        time_window = time_window.get("relative")

    month_names = router_decision.month_names or []
    primary_entity_type = router_decision.primary_entity_type
    primary_entities = router_decision.primary_entities or []
    mode = parsed.get("mode") if isinstance(parsed, dict) else router_decision.mode

    if (
        primary_entity_type == "student"
        and primary_entities
        and mentions_provider
        and mentions_hours
        and time_window == "this_school_year"
        and not month_names
    ):
        mode = "student_provider_year"

    router_decision.mode = mode or router_decision.mode or "district_summary"
    return router_decision
