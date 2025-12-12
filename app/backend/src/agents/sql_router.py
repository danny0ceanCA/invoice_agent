from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import Any, List

import structlog
from openai import OpenAI

from .domain_config_loader import load_domain_config
from .json_utils import _extract_json_object


LOGGER = structlog.get_logger(__name__)


# Deterministic mapping from plan_kinds (intent) to router modes.
# This lets domain_config.json be the source of truth for "what kind of
# report is this?", while still allowing safe fallback when a plan_kind
# is not listed here.
PLAN_KIND_TO_MODE: dict[str, str] = {
    # Student-level monthly spend/hours
    "student_monthly_spend": "student_monthly",
    "student_monthly_hours": "student_monthly",
    # Lists
    "student_list": "student_list",
    "clinician_list": "clinician_list",
    # Invoices
    "student_invoices": "invoice_details",
    "vendor_invoices": "invoice_details",
    # Vendor & district monthly spend
    "vendor_monthly_spend": "vendor_monthly",
    "district_monthly_spend": "district_monthly",
    # Provider breakdown
    "student_provider_breakdown": "student_provider_breakdown",
    # Caseload & clinician/student breakdown
    "caseload": "provider_caseload_monthly",
    "clinician_student_breakdown": "clinician_student_breakdown",
    # Service code / coverage / intensity
    "district_service_code_spend": "district_service_code_monthly",
    "student_service_code_monthly": "student_service_code_monthly",
    "provider_service_code_monthly": "provider_service_code_monthly",
    "student_year_summary": "student_year_summary",
    "student_daily_hours": "student_daily",
    "provider_daily_hours": "provider_daily",
    "district_daily_coverage": "district_daily",
    "student_service_intensity": "student_service_intensity_monthly",
    # Top invoices
    "top_invoices": "top_invoices",
}


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
    # NOTE: plan["kind"] comes from SQL planner and should align with plan_kinds in domain_config.
    plan = sql_plan or {}
    ents = entities or {}
    intent = normalized_intent or {}
    mt = multi_turn_state or {}

    config = load_domain_config()
    router_modes = config.get("router_modes", {})
    print("[DOMAIN-CONFIG-DEBUG][ROUTER] Loaded router_modes:", list(router_modes.keys()))

    primary_type = plan.get("primary_entity_type")
    primary_entities = (
        plan.get("primary_entities") or ents.get(primary_type + "s", []) if primary_type else []
    )

    if not primary_type and isinstance(mt.get("active_topic"), dict):
        primary_type = mt["active_topic"].get("type")

    time_window = plan.get("time_window") or intent.get("time_period", {}).get("relative")
    month_names = plan.get("month_names") or intent.get("time_period", {}).get("month", [])
    date_range = plan.get("date_range") if isinstance(plan.get("date_range"), dict) else None
    metrics = plan.get("metrics") or []

    # Match router modes based on domain_config.router_modes[*].triggers
    q_lower = user_query.lower()
    matched_modes: list[str] = []
    if isinstance(router_modes, dict):
        for mode_key, cfg in router_modes.items():
            triggers = cfg.get("triggers", []) if isinstance(cfg, dict) else []
            for trigger in triggers:
                if isinstance(trigger, str) and trigger.lower() in q_lower:
                    matched_modes.append(mode_key)

    # Deduplicate while preserving order (triggers can add duplicates)
    if matched_modes:
        seen: set[str] = set()
        deduped: list[str] = []
        for m in matched_modes:
            if m in seen:
                continue
            seen.add(m)
            deduped.append(m)
        matched_modes = deduped

    # Prefer a mode derived from the plan kind when available, using
    # PLAN_KIND_TO_MODE as the authoritative mapping from plan_kinds
    # to router modes. This lets domain_config.json lead routing when
    # it has a clear opinion, while still allowing trigger/LLM-based
    # routing as a fallback.
    plan_kind = plan.get("kind") or intent.get("intent")
    plan_kind_mode = PLAN_KIND_TO_MODE.get(plan_kind) if isinstance(plan_kind, str) else None
    print("[DOMAIN-CONFIG-DEBUG][ROUTER] plan_kind:", plan_kind)
    print("[DOMAIN-CONFIG-DEBUG][ROUTER] plan_kind_mode:", plan_kind_mode)

    # ---------------------------------------------------------
    # Ambiguity guard:
    # If the planner implies a single canonical mode via plan_kind,
    # prefer it over other fuzzy matches.
    # ---------------------------------------------------------
    if plan_kind_mode and matched_modes:
        if plan_kind_mode in matched_modes:
            matched_modes = [plan_kind_mode]
    # If triggers found nothing, but plan_kind implies a mode, use it.
    elif plan_kind_mode and not matched_modes:
        matched_modes = [plan_kind_mode]

    prioritized_modes = [
        "invoice_details",
        "top_invoices",
        "student_provider_breakdown",
        "student_monthly",
        "clinician_student_breakdown",
        "district_monthly",
        "vendor_monthly",
        "provider_caseload_monthly",
    ]

    triggered_mode = None
    if matched_modes:
        triggered_mode = matched_modes[0]
        for candidate in matched_modes:
            if candidate in prioritized_modes:
                current_index = prioritized_modes.index(triggered_mode) if triggered_mode in prioritized_modes else len(prioritized_modes)
                candidate_index = prioritized_modes.index(candidate)
                if candidate_index < current_index:
                    triggered_mode = candidate
            else:
                continue

    print("[DOMAIN-CONFIG-DEBUG][ROUTER] matched_modes:", matched_modes)
    print("[DOMAIN-CONFIG-DEBUG][ROUTER] triggered_mode:", triggered_mode)

    # Flags
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

    # Provider breakdown detection should come from domain_config where possible.
    # We combine:
    #   1) plan_kind == "student_provider_breakdown" (authoritative intent), and
    #   2) router_modes.student_provider_breakdown.triggers, if present.
    provider_mode_cfg = router_modes.get("student_provider_breakdown", {}) if isinstance(router_modes, dict) else {}
    provider_triggers = provider_mode_cfg.get("triggers", []) if isinstance(provider_mode_cfg, dict) else []
    provider_trigger_hit = any(
        isinstance(kw, str) and kw.lower() in q_lower for kw in provider_triggers
    )
    needs_provider_breakdown = (
        (plan_kind == "student_provider_breakdown") or provider_trigger_hit
    ) and not top_invoices_intent

    # Modes
    # Prefer plan_kind_mode when available; otherwise fall back to the mode
    # inferred from router_modes triggers. This keeps domain_config.plan_kinds
    # in charge when it has a clear mapping, while still allowing the existing
    # trigger-based routing to handle uncovered cases.
    mode = plan_kind_mode or triggered_mode

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
    elif not mode and primary_type == "student":
        mode = "student_monthly"
    elif not mode and primary_type == "vendor":
        mode = "vendor_monthly"
    elif not mode:
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

    # Note: this is *in addition* to the earlier needs_provider_breakdown flag.
    # Here we focus on conversational follow-ups that clearly imply provider+time.
    mentions_provider = any(t in q_lower for t in [
        "provider", "providers", "clinician", "clinicians"
    ])
    mentions_hours_or_cost = any(t in q_lower for t in [
        "hours", "hour", "cost", "spend", "total"
    ])

    # Pull month from plan or multi-turn
    month_from_state = None
    if isinstance(multi_turn_state, dict):
        month_from_state = multi_turn_state.get("last_month")

    has_month = (
        (month_names and len(month_names) > 0) or
        bool(month_from_state)
    )

    # FINAL SAFE FALLBACK
    # Only override into provider-breakdown / provider-year mode WHEN WE HAVE A MONTH
    # signal from either the planner, NLV, or prior multi-turn state.
    if primary_type == "student" and mentions_provider and mentions_hours_or_cost and has_month:

        if time_window in ["this_school_year", "school_year", "ytd"] and not month_names:
            mode = "student_provider_year"
        else:
            mode = "student_provider_breakdown"

        # Ensure downstream logic_model knows this is a provider breakdown
        # and MUST NOT ask for a specific provider name.
        needs_provider_breakdown = True

        LOGGER.debug("router_safe_provider_override",
                     mode=mode,
                     month=month_names,
                     month_from_state=month_from_state)

    # If NO month is present, NEVER override the router mode.
    # Allow planner + NLV + multi-turn to resolve normally to avoid infinite loops.

    # 1. Resolve a month from user_query text if month_names is empty
    if not month_names:
        # Fallback month detection directly from the fused natural-language query.
        all_months = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]
        for m in all_months:
            if m in q_lower:
                month_names = [m.capitalize()]
                break

    # 2. If still empty, pull from multi_turn_state.last_month
    if not month_names and isinstance(multi_turn_state, dict):
        last_month = multi_turn_state.get("last_month")
        if isinstance(last_month, str) and last_month.strip():
            month_names = [last_month]

    # 3. Ensure month_names is always a list
    if isinstance(month_names, str):
        month_names = [month_names]

    # ------------------------------------------------------------------
    # TERMINAL RULE FOR DISTRICT-WIDE PROVIDER BREAKDOWN
    #
    # Queries like:
    #   "which agencies provide support to our students"
    #
    # are routed as student_provider_breakdown at the district level with
    # no specific primary entity. In that case, we only want to run a
    # single-stage query that answers:
    #   - which vendors, and
    #   - how much was paid in total.
    #
    # There is no second stage, so we must NOT keep
    # needs_provider_breakdown=True, or the agent loop will re-run the
    # same RouterDecision over and over until the iteration limit.
    #
    # So: if this is a district-scope provider breakdown (no primary
    # entity), force needs_provider_breakdown = False so the workflow
    # terminates after one SQL pass.
    # ------------------------------------------------------------------
    if (
        mode == "student_provider_breakdown"
        and primary_type == "district"
        and not primary_entities
    ):
        needs_provider_breakdown = False

    router_decision = RouterDecision(
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

    print("[MV-DEBUG] ROUTER_DECISION MODE:", router_decision.mode)
    print("[MV-DEBUG] ROUTER SQL_TEMPLATE_HINT:", "SQL_TEMPLATE_HINT:")

    return router_decision


def build_sql_router_system_prompt() -> str:
    """System prompt for AI-driven routing of semantic SQL plans."""

    config = load_domain_config()
    router_modes = config.get("router_modes", {})

    return f"""
ROUTER_MODES CONFIGURATION (read-only):
{json.dumps(router_modes, indent=2)}

Use the JSON router_modes triggers to interpret user intent. 
Do not override RouterDecision fallback logic when JSON triggers 
do not match.

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

    # SHORT-CIRCUIT: if the deterministic router has already identified a
    # student-scoped provider breakdown, do NOT let the LLM router override it.
    # This prevents the router model from downgrading the mode and causing
    # follow-ups like "provider by hours for July" to ask for a specific
    # provider instead of returning a full provider breakdown.
    if (
        fallback_decision.primary_entity_type == "student"
        and fallback_decision.primary_entities
        and fallback_decision.needs_provider_breakdown
        and fallback_decision.mode in {"student_provider_breakdown", "student_provider_year"}
    ):
        LOGGER.debug(
            "router_short_circuit_student_provider_breakdown",
            mode=fallback_decision.mode,
            primary_entities=fallback_decision.primary_entities,
            month_names=fallback_decision.month_names,
            time_window=fallback_decision.time_window,
        )
        return fallback_decision

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
        try:
            assistant_content = response.choices[0].message.content if response.choices else None
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("llm_missing_content", error=str(exc))
            raise

        parsed = _extract_json_object(assistant_content or "{}")
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
