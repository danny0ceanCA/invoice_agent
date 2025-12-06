"""Shared JSON extraction utilities for agent model responses."""

from __future__ import annotations

import json
import re

import structlog

LOGGER = structlog.get_logger(__name__)


def _extract_json_object(raw: str) -> dict:
    """
    Safely extract a single JSON object from an LLM response string.

    - Trims whitespace.
    - Finds the first {...} block using a regex.
    - Parses that block as JSON.
    - Raises ValueError if no JSON object is found.
    """
    if raw is None:
        raise ValueError("LLM returned empty content")

    text = raw.strip()
    # Find the first JSON object in the string
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        LOGGER.warning("llm_missing_json_object", raw_preview=text[:500])
        raise ValueError("LLM did not return a JSON object")

    json_str = match.group(0)
    try:
        return json.loads(json_str)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("llm_json_parse_failed", error=str(exc), raw_preview=json_str[:500])
        raise
