"""SQL planning stage for the district analytics agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import structlog
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from .domain_config_loader import load_domain_config
from .json_utils import _extract_json_object

LOGGER = structlog.get_logger(__name__)


def build_sql_planner_system_prompt() -> str:
    """System prompt for the SQL planner stage."""

    config = load_domain_config()
    plan_kinds = config.get("plan_kinds", {}) if isinstance(config, dict) else {}
    plan_kinds_json = json.dumps(plan_kinds, indent=2)

    base_prompt = """
You are the SQL Planning Model for the CareSpend / SCUSD District Analytics Agent.

Your role is SEMANTIC PLANNING ONLY.
You DO NOT write SQL. You DO NOT guess SQL. You DO NOT check SQL.
You ONLY output a machine-readable query plan.

===============================================================
INPUT FORMAT

You receive:
{
"query": "...raw natural language...",
"normalized_intent": {... from NLV and entity resolver ...},
"entities": {
"students": [...],
"providers": [...],
"clinicians": [...],
"vendors": [...],
"ambiguous_names": [...]
},
"context": { "district_key": "...", ... }
}

===============================================================
OUTPUT FORMAT

Return EXACTLY one JSON object:

{
"plan": {
"kind": "...",
"primary_entity_type": "...",
"primary_entities": [...],
"time_window": "...",
"month_names": [...],
"date_range": {
"start_date": "...",
"end_date": "..."
},
"metrics": [...],
"group_by": [...],
"needs_trend_detection": false
},
"requires_clarification": false,
"clarification_needed": []
}

If any required element is missing → requires_clarification=true.

===============================================================
SCHOOL YEAR / DATE NORMALIZATION

Normalize phrases:
"this school year" → time_window="school_year"
"school year" → time_window="school_year"
"year-to-date" → time_window="ytd"
"YTD" → time_window="ytd"
"last three months" → time_window="last_3_months"
"name a month (July…December)" → month_names=[...]

Date-range guidance:
- For time_window = "school_year" or "this_school_year", leave date_range.start_date and date_range.end_date as null unless the user provided explicit calendar dates. Treat time_window as semantic metadata only.
- Only populate date_range when the user supplied explicit dates (e.g., "between August 1 and October 31") or explicit calendar years (e.g., "in 2025").
- Do NOT invent default calendar years; never assume a July 1..June 30 window without user-provided dates.
- The logic model will convert time_window and (optional) date_range into actual SQL predicates. When date_range is null, the logic model may omit invoice_date filters entirely.

===============================================================
METRIC NORMALIZATION

If query includes:

“spend”, “cost”, “charges”, “burn rate” → metrics=["total_cost"]

“hours”, “time worked”, “service hours” → metrics=["total_hours"]

If ambiguous → clarification required.

===============================================================
ENTITY RESOLUTION DEPENDENCE

Use entities from entity resolver:

If exactly one student:
primary_entity_type="student"
If exactly one vendor:
primary_entity_type="vendor"
If exactly one clinician:
primary_entity_type="clinician"
If none:
primary_entity_type="district"

If ambiguous:
requires_clarification=true
clarification_needed=["student_name" | "provider_name" | "vendor_name"]

===============================================================
PROVIDER / CLINICIAN NORMALIZATION

- The database does NOT contain any column named “provider”. All provider queries must be rewritten to target the column `ili.clinician`.
- If the user asked for “provider(s)”, use the clinician column.
- Do not emit SQL that references a provider column.
- When the plan indicates a provider query, the SELECT fields must be “clinician” or an alias like “clinician AS provider”.

===============================================================
MAPPING NATURAL LANGUAGE → PLAN KIND

Use the provided PLAN_KINDS configuration to interpret the user's analytic intent. plan_kinds defines semantic categories, synonyms, and expected entity roles.

PLAN_KINDS:
"""

    closing_prompt = """

===============================================================
AMBIGUITY RULES (STRICT)

If missing any of:

student_name

vendor_name

clinician_name

time window

month

metric

Set:
"requires_clarification": true

===============================================================
ABSOLUTE RULES

Do NOT guess names.

Do NOT assume time ranges.

Do NOT infer relationships not stated (student + vendor does NOT imply linkage).

Do NOT insert schema columns.

Do NOT produce SQL.

===============================================================
SCHOOL YEAR SQL RULES:

• When NLV has flagged a school-year period (start_date, end_date),
  you MUST use those exact normalized boundaries in SQL:

    WHERE invoice_date BETWEEN :start_date AND :end_date

• NEVER substitute calendar-year ranges unless the user explicitly requests them.

• If the user says “this year” and NO explicit dates are supplied,
  you MUST generate a SQL plan using the school-year boundaries from NLV.

==============================================================
END OF RULES
"""

    return f"{base_prompt}{plan_kinds_json}{closing_prompt}"


_TEMPLATES_DIR = Path(__file__).parent / "sql_templates"
_ENV = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=False)


def render_template(template_name: str, context: Mapping[str, Any]) -> str:
    """Render a SQL template with the provided context."""

    template = _ENV.get_template(template_name)
    return template.render(context)


def route_sql_template(
    *, intent: str, entities: dict[str, Any] | None, time_period: dict[str, Any] | None
) -> str:
    """Select and render the SQL template for the given intent."""

    entities = entities or {}
    time_period = time_period or {}

    # Detect invoice-details-by-month-for-student
    if (
        intent == "invoice_details"
        and entities.get("student_name")
        and time_period.get("month")
    ):

        print("[sql-planner] ROUTE invoice_details_month_student", flush=True)
        print("[sql-planner-debug] student_month_template", flush=True)

        return render_template(
            "invoice_details_month_student.sql",
            {
                "student_name": entities["student_name"],
                "month": time_period["month"],
                "start_date": time_period["start_date"],
                "end_date": time_period["end_date"],
            }
        )

    if intent == "invoice_details" and entities.get("student_name"):
        print("[sql-planner] ROUTE invoice_details_student_year", flush=True)
        return render_template(
            "invoice_details_student_year.sql",
            {
                "student_name": entities["student_name"],
                "start_date": time_period.get("start_date"),
                "end_date": time_period.get("end_date"),
            },
        )

    if intent == "invoice_details":
        print("[sql-planner] ROUTE invoice_details_year", flush=True)
        return render_template(
            "invoice_details_year.sql",
            {
                "start_date": time_period.get("start_date"),
                "end_date": time_period.get("end_date"),
            },
        )

    print("[sql-planner] ROUTE invoice_summary", flush=True)
    return render_template("invoice_summary.sql", {})


def run_sql_planner_model(
    *,
    user_query: str,
    normalized_intent: dict[str, Any],
    entities: dict[str, Any],
    user_context: dict[str, Any],
    client: OpenAI,
    model: str,
    system_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """Execute the SQL planner model and return a semantic plan."""

    inferred_plan_kind = None
    try:
        config = load_domain_config()
        plan_kinds = config.get("plan_kinds", {}) if isinstance(config, dict) else {}
        print("[DOMAIN-CONFIG-DEBUG][PLANNER] Loaded plan_kinds:", list(plan_kinds.keys()))
        print("[DOMAIN-CONFIG-DEBUG][PLANNER] inferred_plan_kind:", inferred_plan_kind)
        print("[DOMAIN-CONFIG-DEBUG][PLANNER] Example synonyms:", {
            k: v.get("intent_synonyms", [])[:2] for k, v in list(plan_kinds.items())[:3]
        })
    except Exception:
        plan_kinds = {}

    query_lower = user_query.lower() if isinstance(user_query, str) else ""
    if isinstance(plan_kinds, dict) and query_lower:
        for plan_kind, plan_kind_config in plan_kinds.items():
            synonyms = []
            if isinstance(plan_kind_config, dict):
                intent_synonyms = plan_kind_config.get("intent_synonyms")
                if isinstance(intent_synonyms, list):
                    synonyms = intent_synonyms

            for synonym in synonyms:
                if isinstance(synonym, str) and synonym.lower() in query_lower:
                    inferred_plan_kind = plan_kind
                    break

            if inferred_plan_kind:
                break

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": user_query,
                    "normalized_intent": normalized_intent or {},
                    "entities": entities or {},
                    "context": user_context or {},
                    "inferred_plan_kind": inferred_plan_kind,
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
        if not isinstance(parsed, dict):
            raise ValueError("Invalid planner response")
    except Exception as exc:
        LOGGER.warning("planner_model_failed", error=str(exc))
        return {
            "plan": None,
            "requires_clarification": False,
            "clarification_needed": [],
        }

    payload: dict[str, Any] = {
        "plan": parsed.get("plan"),
        "requires_clarification": bool(parsed.get("requires_clarification", False)),
        "clarification_needed": parsed.get("clarification_needed", []),
    }

    if not isinstance(payload.get("clarification_needed"), list):
        payload["clarification_needed"] = []

    plan = payload.get("plan")
    entities = entities or {}
    normalized_intent = normalized_intent or {}

    plan_kind_value = plan.get("kind") if isinstance(plan, dict) else None
    plan_kind_missing = not isinstance(plan_kind_value, str) or plan_kind_value == ""
    plan_kind_in_config = isinstance(plan_kinds, dict) and isinstance(plan_kind_value, str) and plan_kind_value in plan_kinds

    if inferred_plan_kind is not None:
        if plan_kind_missing:
            plan = plan if isinstance(plan, dict) else {}
            plan["kind"] = inferred_plan_kind
        elif not plan_kind_in_config:
            plan = plan if isinstance(plan, dict) else {}
            plan["kind"] = inferred_plan_kind

    time_period = (
        normalized_intent.get("time_period")
        if isinstance(normalized_intent, dict)
        else {}
    )
    month_name = time_period.get("month") if isinstance(time_period, dict) else None
    explicit_month_mentioned = False
    if isinstance(month_name, list):
        explicit_month_mentioned = bool(month_name)
    elif isinstance(month_name, str):
        explicit_month_mentioned = True
    year_value = time_period.get("year") if isinstance(time_period, dict) else None
    start_date = time_period.get("start_date") if isinstance(time_period, dict) else None
    end_date = time_period.get("end_date") if isinstance(time_period, dict) else None

    if normalized_intent.get("time_period", {}).get("relative") == "this_school_year":
        tp = normalized_intent["time_period"]
        if not isinstance(plan, dict):
            plan = plan or {}
        if isinstance(tp.get("start_date"), str) and isinstance(tp.get("end_date"), str):
            plan["date_range"] = {
                "start_date": tp["start_date"],
                "end_date": tp["end_date"],
            }
        if not explicit_month_mentioned:
            plan["month_names"] = []

    if isinstance(year_value, str) and year_value.isdigit():
        year_value = int(year_value)

    clar_needed = payload.get("clarification_needed")
    clar_needed = clar_needed if isinstance(clar_needed, list) else []

    if isinstance(start_date, str) and isinstance(end_date, str):
        if not isinstance(plan, dict):
            plan = {}
        plan["date_range"] = {"start_date": start_date, "end_date": end_date}
        if isinstance(time_period.get("relative"), str):
            plan.setdefault("time_window", time_period.get("relative"))
        clar_needed = [item for item in clar_needed if item != "time_period"]
        payload["plan"] = plan

    if isinstance(month_name, str) and year_value is not None:
        if not isinstance(plan, dict):
            plan = {}

        plan.setdefault("date_range", {})
        plan["month_names"] = [month_name]

        if isinstance(start_date, str) and isinstance(end_date, str):
            plan["date_range"] = {"start_date": start_date, "end_date": end_date}

        if isinstance(time_period.get("relative"), str):
            plan.setdefault("time_window", time_period.get("relative"))

        clar_needed = [item for item in clar_needed if item != "time_period"]

        payload["plan"] = plan

    payload["clarification_needed"] = clar_needed
    payload["requires_clarification"] = bool(clar_needed)

    if isinstance(plan, dict):
        vendor_entities = (
            entities.get("vendors")
            if isinstance(entities.get("vendors"), list)
            else []
        )
        student_entities = (
            entities.get("students")
            if isinstance(entities.get("students"), list)
            else []
        )

        time_range = (
            normalized_intent.get("time_range")
            if isinstance(normalized_intent, dict)
            else None
        )

        if isinstance(time_range, dict):
            start_date = time_range.get("start_date")
            end_date = time_range.get("end_date")
            has_dates = isinstance(start_date, str) and isinstance(end_date, str)
            plan_date_range = plan.get("date_range")
            existing_date_range = plan_date_range if isinstance(plan_date_range, dict) else {}

            if has_dates and not (
                isinstance(existing_date_range.get("start_date"), str)
                and isinstance(existing_date_range.get("end_date"), str)
            ):
                plan["date_range"] = {
                    "start_date": start_date,
                    "end_date": end_date,
                }

        primary_entity_type = plan.get("primary_entity_type")

        if primary_entity_type == "vendor":
            plan["primary_entities"] = list(vendor_entities)

        if plan.get("primary_entity_type") == "student":
            plan["primary_entities"] = [
                entity
                for entity in plan.get("primary_entities", [])
                if entity not in vendor_entities
            ]
            if student_entities and not plan.get("primary_entities"):
                plan["primary_entities"] = list(student_entities)
            for vendor_key in ("vendor_name", "vendor", "vendors"):
                plan.pop(vendor_key, None)

        if plan.get("primary_entity_type") != "vendor":
            for vendor_key in ("vendor_name", "vendor", "vendors"):
                plan.pop(vendor_key, None)

        payload["plan"] = plan
    else:
        payload["plan"] = None

    return payload
