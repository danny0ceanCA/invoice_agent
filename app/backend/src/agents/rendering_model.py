"""Rendering-stage helpers for the analytics agent.

Refactor note: extracted rendering concerns to clarify the two-model flow
without changing the existing user-facing output behavior.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .ir import AnalyticsIR


def build_rendering_system_prompt() -> str:
    return (
        "You render user-facing responses for the district analytics agent. "
        "Given a user query and structured analytics IR, produce clear natural-language text."
    )


def run_rendering_model(
    *,
    user_query: str,
    ir: AnalyticsIR,
    client: OpenAI,
    model: str,
    system_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """
    Render the final payload from the logic IR.

    The current implementation is a pass-through to preserve backward-compatible
    behavior while keeping the separation between logic and rendering explicit.
    """

    _ = (client, model, system_prompt, temperature, user_query)  # preserve signature for future use
    return ir.to_payload()
