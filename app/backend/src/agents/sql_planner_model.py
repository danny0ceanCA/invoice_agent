"""SQL planning stage for the district analytics agent."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


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

Define SCUSD school year as:

school_year:
start_date = July 1 of the school year
end_date = June 30 of the following year

Normalize phrases:
"this school year" → time_window="school_year"
"school year" → time_window="school_year"
"year-to-date" → time_window="ytd"
"YTD" → time_window="ytd"
"last three months" → time_window="last_3_months"
"name a month (July…December)" → month_names=[...]

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
END OF RULES
"""


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
