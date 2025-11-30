"""Intermediate representation helpers for the analytics agent.

Refactor note: extracted IR parsing to separate the logic and rendering stages
without changing the agent's existing behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel


class AnalyticsEntities(BaseModel):
    """Entities referenced by the analytics logic stage."""

    students: list[str] = []
    providers: list[str] = []
    vendors: list[str] = []
    invoices: list[str] = []


class AnalyticsIR(BaseModel):
    """Logic-stage output capturing structured analytics intent and results."""

    text: str = ""
    select: list[Any] | None = None
    rows: list[dict[str, Any]] | None = None
    html: str | None = None
    entities: AnalyticsEntities | None = None
    rows_field_present: bool = True

    def to_payload(self) -> dict[str, Any]:
        """Return a mapping compatible with the existing rendering pipeline."""

        payload: dict[str, Any] = {"text": self.text, "html": self.html}
        if self.select is not None:
            payload["select"] = self.select
        if self.rows_field_present:
            payload["rows"] = self.rows
        if self.entities is not None:
            payload["entities"] = self.entities.model_dump()
        return payload


def _coerce_rows(candidate: Any) -> list[dict[str, Any]] | None:
    if isinstance(candidate, list) and all(isinstance(item, Mapping) for item in candidate):
        return [dict(item) for item in candidate]  # type: ignore[arg-type]
    return None


def _payload_to_ir(payload: Any, last_rows: list[dict[str, Any]] | None = None) -> AnalyticsIR:
    """Convert raw model output into the structured IR, preserving fallbacks."""

    if isinstance(payload, Mapping):
        entities_obj: AnalyticsEntities | None = None
        entities_raw = payload.get("entities")
        if isinstance(entities_raw, Mapping):
            try:
                entities_obj = AnalyticsEntities.model_validate(dict(entities_raw))
            except Exception:
                entities_obj = None

        rows_present = "rows" in payload
        text_value = str(payload.get("text") or "").strip()
        html_value = payload.get("html") if isinstance(payload.get("html"), str) else None
        rows_value = _coerce_rows(payload.get("rows"))
        return AnalyticsIR(
            text=text_value,
            select=payload.get("select") if isinstance(payload.get("select"), list) else None,
            rows=rows_value,
            html=html_value,
            entities=entities_obj,
            rows_field_present=rows_present,
        )

    if isinstance(payload, str):
        return AnalyticsIR(text=payload.strip(), rows=last_rows, rows_field_present=True)

    rows_candidate = _coerce_rows(payload)
    if rows_candidate is not None:
        return AnalyticsIR(text="", rows=rows_candidate, rows_field_present=True)

    return AnalyticsIR(text=str(payload).strip(), rows=last_rows, rows_field_present=True)
