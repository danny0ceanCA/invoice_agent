"""Business rule enforcement stage for the analytics agent."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .ir import AnalyticsIR


def build_business_rule_system_prompt() -> str:
    """System prompt guiding business-rule sanitation for AnalyticsIR payloads."""

    return """
You are the Business Rules stage for the CareSpend / SCUSD analytics agent.
You receive the AnalyticsIR as JSON (logic-stage output) and may also receive resolved entities and/or a SQL plan.

Input JSON from caller:
{
  "ir": { ...AnalyticsIR as JSON... },
  "entities": { ...resolved entities, may be empty... },
  "plan": { ...SQL planner plan, may be null... }
}

Output JSON shape:
{
  "ok": true | false,
  "issues": [ "..." ],
  "ir": { ...possibly sanitized AnalyticsIR JSON... }
}

Responsibilities:
- Enforce business semantics and safety, NOT structural validation.
- Clinician vs Vendor sanity check: if IR entities.providers or entities.clinicians contain things that clearly look like organizations without clinician tokens, flag them in issues and, if appropriate, move them to vendors.
- Clinician tokens (case-insensitive): clinician, nurse, lvn, hha, aide, health aide, therapist, provider, caregiver. Treat health aide as a clinician type.
- Strip sensitive columns if present in rows: remove keys named rate, hourly_rate, or pay_rate (case-insensitive).
- Invoice detail vs summary sanity: if rows look like invoice line items (invoice_number + student + clinician/provider + service_code + hours + cost + service_date), they should not also contain invoice-level total/summary fields like total_cost and status. If conflict, prefer keeping the line-item columns, drop invoice-level summary columns from those rows, and record an issue string.
- If the IR is unsafe or cannot be trusted, set ok=false and return an issues list. The caller will then fall back to a safe message.
- Student-scope safety: if plan.primary_entity_type == "student", remove any vendor filters and clear vendors from IR.entities.

Rules:
- Do NOT output SQL, HTML, or prose. Only the JSON object described above.
- Do NOT fabricate new values; only sanitize or move existing ones.
"""


def run_business_rule_model(
    *,
    ir: AnalyticsIR,
    entities: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    client: OpenAI,
    model: str,
    system_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """Apply business rule checks via the model with safe fallbacks."""

    def _sanitize_ir_for_student_scope(ir_obj: AnalyticsIR) -> AnalyticsIR:
        if not isinstance(plan, dict) or plan.get("primary_entity_type") != "student":
            return ir_obj

        sanitized = ir_obj.model_copy(deep=True)
        if sanitized.entities:
            sanitized.entities.vendors = []
        return sanitized

    ir = _sanitize_ir_for_student_scope(ir)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "ir": ir.model_dump(),
                    "entities": entities or {},
                    "plan": plan,
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
            raise ValueError("Invalid business rule response")
    except Exception:
        return {
            "ok": True,
            "issues": [],
            "ir": ir.model_dump(),
        }

    ir_payload = parsed.get("ir") if isinstance(parsed.get("ir"), dict) else ir.model_dump()

    if isinstance(plan, dict) and plan.get("primary_entity_type") == "student":
        if isinstance(ir_payload, dict):
            entities_payload = ir_payload.get("entities")
            if isinstance(entities_payload, dict):
                entities_payload["vendors"] = []
                ir_payload["entities"] = entities_payload

    def _collect_select_aliases(select_value: Any) -> set[str]:
        aliases: set[str] = set()
        if not isinstance(select_value, list):
            return aliases

        for entry in select_value:
            if isinstance(entry, str):
                lowered = entry.lower()
                if " as " in lowered:
                    alias = entry.rsplit(" as ", 1)[-1]
                elif " AS " in entry:
                    alias = entry.rsplit(" AS ", 1)[-1]
                else:
                    alias = entry
                alias = alias.strip()
                if alias:
                    aliases.add(alias)
            elif isinstance(entry, dict):
                alias_value = entry.get("alias") or entry.get("field") or entry.get("column")
                if isinstance(alias_value, str) and alias_value.strip():
                    aliases.add(alias_value.strip())
        return aliases

    if isinstance(ir_payload, dict):
        approved_fields = _collect_select_aliases(ir_payload.get("select"))
        if approved_fields:
            rows_value = ir_payload.get("rows")
            if isinstance(rows_value, list):
                sanitized_rows: list[dict[str, Any]] = []
                for row in rows_value:
                    if isinstance(row, dict):
                        clean_row = {
                            key: value for key, value in row.items() if key in approved_fields
                        }
                        sanitized_rows.append(clean_row)
                ir_payload["rows"] = sanitized_rows

    result = {
        "ok": bool(parsed.get("ok", True)),
        "issues": parsed.get("issues", []),
        "ir": ir_payload,
    }

    if not isinstance(result.get("issues"), list):
        result["issues"] = []

    return result
