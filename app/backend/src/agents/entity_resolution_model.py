"""Entity resolution stage for the district analytics agent."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


def build_entity_resolution_system_prompt() -> str:
    """System prompt for resolving entities and refining intent."""

    return """
You are the Entity Resolution stage for the district analytics agent.
Input: a JSON object shaped like:
{
  "query": "...raw user query...",
  "normalized_intent": { ... from NLV model ... },
  "context": { ... user_context ... }
}

Output: machine-readable JSON ONLY. No prose. No SQL. No HTML.
Expected shape (flexible but consistent):
{
  "normalized_intent": { ...refined version... },
  "entities": {
    "students": [ "..." ],
    "providers": [ "..." ],
    "clinicians": [ "..." ],
    "vendors": [ "..." ],
    "districts": [ "..." ],
    "ambiguous_names": [ "..." ]
  },
  "requires_clarification": false,
  "clarification_needed": [ "student_name" | "provider_name" | "vendor_name" | "time_period" | "scope", ... ],
  "entity_warnings": [ "..." ]
}

Rules:
- Preserve anything useful from the incoming normalized_intent (intent, time_period, scope, existing entities), only refining or expanding where helpful.
- Always return strictly JSON output parsable by json.loads.

Clinician vs Vendor classification (apply exactly as written):
- Only classify an entity as a clinician (or provider) if its name, title, or description contains one of these terms (case-insensitive, word-level or clear substring): clinician, nurse, lvn, hha, aide, health aide, therapist, provider, caregiver.
- Otherwise, default to treating the entity as a vendor/organization (or generic “provider organization”) rather than an individual clinician.
- Treat “health aide” (and variations like “health aide”, “health-aide”) as a kind of clinician.
- If a name looks like a person (e.g., First Last) but does not contain any of those clinician terms, still treat it as a student by default, not a vendor.
- If an entity string is multi-word with “Services”, “Care”, “Agency”, “LLC”, “Inc”, etc. and no clinician tokens, treat it as a vendor/organization, not a clinician.
- For ambiguous short names like “Addison”, do not guess student vs clinician vs vendor; instead add to ambiguous_names, set requires_clarification=true, and add "student_name" to clarification_needed (and/or provider_name if appropriate).
"""


def _default_payload(normalized_intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "normalized_intent": normalized_intent or {},
        "entities": {},
        "requires_clarification": False,
        "clarification_needed": [],
        "entity_warnings": [],
    }


def run_entity_resolution_model(
    *,
    user_query: str,
    normalized_intent: dict[str, Any],
    user_context: dict[str, Any],
    client: OpenAI,
    model: str,
    system_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """Execute the entity resolution model with safe fallbacks."""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": user_query,
                    "normalized_intent": normalized_intent or {},
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
            return _default_payload(normalized_intent)
    except Exception:
        return _default_payload(normalized_intent)

    payload = _default_payload(normalized_intent)
    payload.update(parsed)

    if not isinstance(payload.get("entities"), dict):
        payload["entities"] = {}

    if not isinstance(payload.get("clarification_needed"), list):
        payload["clarification_needed"] = []

    if not isinstance(payload.get("entity_warnings"), list):
        payload["entity_warnings"] = []

    if not payload.get("normalized_intent"):
        payload["normalized_intent"] = normalized_intent or {}

    return payload
