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
  "context": { ... user_context ... },
  "known_entities": {
    "students": [list of district students],
    "vendors": [list of district vendors],
    "clinicians": [list of district clinicians]
  }
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

Entity classification rules:
- Use known_entities as the universe of valid students, vendors, and clinicians, but you may fuzzy match user-supplied names against those lists.
- Fuzzy matching rules (case-insensitive):
  • exact equality
  • one name contains the other (user_name contains known_name or known_name contains user_name)
- If a user-supplied name has exactly one good fuzzy match in a known_entities list, treat it as that entity.
- If a name matches multiple entities equally well, add it to ambiguous_names, set requires_clarification=true, and include the appropriate clarification_needed entry (e.g., "vendor_name" or "student_name").
- If a name does not fuzzily match anything in known_entities, set requires_clarification=true and include "vendor_name" / "student_name" / "clinician_name" as appropriate.
- Vendors are recognized when the string looks like an organization: contains tokens like services, care, agency, llc, inc, corporation, etc. Do NOT classify a string as a vendor if it looks like a personal/student name or lacks those vendor tokens.
- Clinicians are ONLY recognized when the name or title includes: clinician, nurse, lvn, hha, aide, health aide, therapist, provider, caregiver. Treat “health aide” (and variations like “health-aide”) as a clinician type.
- If a name looks like a person (e.g., First Last) and lacks clinician tokens, treat it as a student (or ambiguous) — never a vendor.
- For ambiguous short names like “Addison”, do not guess; add to ambiguous_names, set requires_clarification=true, and include "student_name" (and/or provider_name if appropriate) in clarification_needed.
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
    known_entities: dict[str, list[str]] | None,
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
                    "known_entities": known_entities or {},
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
