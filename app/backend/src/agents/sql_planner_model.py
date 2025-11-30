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

    payload = {
        "plan": parsed.get("plan"),
        "requires_clarification": bool(parsed.get("requires_clarification", False)),
        "clarification_needed": parsed.get("clarification_needed", []),
    }

    if not isinstance(payload.get("clarification_needed"), list):
        payload["clarification_needed"] = []

    return payload
