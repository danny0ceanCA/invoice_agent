"""SQL planning stage for the district analytics agent."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


def build_sql_planner_system_prompt() -> str:
    """System prompt for the SQL planner stage."""

    return """
You are the SQL planning stage for the district analytics agent. You plan the query semantics but do NOT execute SQL.

Input JSON from the user:
{
  "query": "...raw user query...",
  "normalized_intent": { ...from NLV/entity... },
  "entities": { ...resolved entities from entity model... },
  "context": { ...user_context... }
}

Output: machine-readable JSON ONLY, for example:
{
  "plan": {
    "kind": "student_monthly_spend" | "student_ytd_spend" | "vendor_monthly_spend" | "clinician_trend" | "district_monthly_hours" | null,
    "primary_entity_type": "student" | "vendor" | "clinician" | "district" | null,
    "primary_entities": [ "..." ],
    "time_window": "school_year" | "this_school_year" | "ytd" | "last_3_months" | "month" | null,
    "month_names": [ "july", "august", ... ],
    "date_range": {
      "start_date": "YYYY-MM-DD" | null,
      "end_date": "YYYY-MM-DD" | null
    },
    "metrics": [ "total_cost", "total_hours" ],
    "group_by": [ "student", "vendor", "clinician", "month" ],
    "needs_trend_detection": false
  },
  "requires_clarification": false,
  "clarification_needed": [ "student_name", "time_period", "vendor_name", "clinician_name", ... ]
}

Guidance:
- Normalize phrases like "this school year" -> time_window="school_year" (optionally provide date_range), "year to date" -> time_window="ytd", "over the last three months" -> time_window="last_3_months".
- If the plan cannot be confidently determined, set plan.kind = null, requires_clarification = true, and fill clarification_needed with specific missing items.
- Do NOT copy or restate database schema or canonical SQL rules; the logic stage handles SQL generation.
- Vendor scope rules (strict): vendor filters are ONLY allowed when (a) the normalized intent is vendor-scoped (intent in ["vendor_monthly_spend", "vendor_hours", "compare_vendors"] or primary_entity_type="vendor") AND (b) entity resolution returned at least one vendor name. Student or clinician names MUST NOT trigger vendor filters.
- If primary_entity_type="student", do NOT add vendors to primary_entities and never add vendor_name. If both students and vendors are present, primary_entity_type MUST be "vendor".
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
