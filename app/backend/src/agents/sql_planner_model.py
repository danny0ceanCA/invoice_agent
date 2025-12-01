"""SQL planning stage for the district analytics agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from openai import OpenAI
from jinja2 import Environment, FileSystemLoader


def build_sql_planner_system_prompt() -> str:
    """System prompt for the SQL planner stage."""

    return """
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

STUDENT REPORTS

"monthly spend for <student>" → student_monthly_spend

"monthly hours for <student>" → student_monthly_hours

"YTD spend for <student>" → student_ytd_spend

"YTD hours for <student>" → student_ytd_hours

"all invoices for <student>" → student_invoices

VENDOR REPORTS

"monthly spend for <vendor>" → vendor_monthly_spend

"YTD spend for <vendor>" → vendor_ytd_spend

"invoices for <vendor>" → vendor_invoices

CLINICIAN REPORTS

"highest hours for clinicians" → clinician_hours_ranking

"monthly hours for clinicians" → clinician_monthly_hours

DISTRICT REPORTS

"district-wide monthly spend" → district_monthly_spend

"district-wide monthly hours" → district_monthly_hours

"district YTD spend" → district_ytd_spend

COMPARISON REPORTS

"compare X and Y" → comparison
primary_entities=[X,Y]
group_by=["month"]

TREND REPORTS

“increasing”, “decreasing”, “trend”, “over time” →
needs_trend_detection=true

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

    vendor_intent_kinds = {"vendor_monthly_spend", "vendor_hours", "compare_vendors"}

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
        if not isinstance(parsed, dict):
            raise ValueError("Invalid planner response")
    except Exception:
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

    intent_value = normalized_intent.get("intent") if isinstance(normalized_intent, dict) else None
    intent_vendor_scoped = bool(
        isinstance(intent_value, str)
        and intent_value in vendor_intent_kinds
    )
    intent_primary_entity_type = (
        normalized_intent.get("primary_entity_type")
        if isinstance(normalized_intent, dict)
        else None
    )
    normalized_vendor_scope = intent_vendor_scoped or intent_primary_entity_type == "vendor"
    vendor_filter_allowed = normalized_vendor_scope and bool(vendor_entities)

    if isinstance(plan, dict):
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

        if vendor_filter_allowed:
            plan["primary_entity_type"] = "vendor"
            plan["primary_entities"] = list(vendor_entities)

        # If vendor filtering is not allowed, strip any vendor scope.
        if not vendor_filter_allowed and primary_entity_type == "vendor":
            if student_entities:
                plan["primary_entity_type"] = "student"
                plan["primary_entities"] = list(student_entities)
            else:
                plan["primary_entity_type"] = None
                plan["primary_entities"] = []

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

        if not vendor_filter_allowed:
            for vendor_key in ("vendor_name", "vendor", "vendors"):
                plan.pop(vendor_key, None)

        payload["plan"] = plan
    else:
        payload["plan"] = None

    return payload
