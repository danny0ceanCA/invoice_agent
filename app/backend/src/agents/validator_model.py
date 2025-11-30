"""Validation pass for analytics IR outputs.

The validator is intentionally lightweight and defensive. It attempts to
standardize the IR, flag obvious safety/formatting issues, and avoid blocking
existing flows unless there is a clear structural or safety problem.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .ir import AnalyticsIR

_SQL_PATTERN = re.compile(r"\b(SELECT|WITH|UPDATE|DELETE|INSERT|FROM|WHERE)\b", re.IGNORECASE)
_HTML_PATTERN = re.compile(r"<[^>]+>")


class _ValidatedIRWrapper:
    """Duck-type wrapper to attach metadata without altering AnalyticsIR.

    The rendering model only calls ``model_dump`` and reads ``rows``; wrapping
    keeps compatibility while letting us surface validator metadata (e.g.,
    version/task/decision) and optional insights later in the pipeline.
    """

    def __init__(self, ir: AnalyticsIR, *, metadata: Mapping[str, Any] | None = None):
        self._ir = ir
        self.rows = ir.rows
        self._metadata = dict(metadata or {})

    def model_dump(self) -> dict[str, Any]:
        data = self._ir.model_dump()
        data.update(self._metadata)
        return data

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - passthrough
        return getattr(self._ir, item)


def _strip_html(text: str) -> str:
    return _HTML_PATTERN.sub("", text or "").strip()


def run_validator_model(ir: AnalyticsIR) -> dict[str, Any]:
    """Validate and lightly correct the AnalyticsIR before rendering.

    Returns a dict with keys:
    - ``valid``: bool indicating if the IR passed checks
    - ``issues``: list of strings describing detected problems
    - ``ir``: sanitized AnalyticsIR (wrapper preserves compatibility)
    - ``metadata``: supplemental fields (version/task/decision) injected when missing
    """

    issues: list[str] = []
    sanitized_ir = ir

    metadata: dict[str, Any] = {}
    base_dump = ir.model_dump()

    # Ensure required metadata keys exist; default them without blocking flows.
    metadata.setdefault("version", base_dump.get("version", "1.0"))
    metadata.setdefault("task", base_dump.get("task", "analytics"))
    metadata.setdefault("decision", base_dump.get("decision", "render"))

    # rows must be list[Mapping] or None
    if ir.rows is not None:
        if not isinstance(ir.rows, list) or not all(isinstance(item, Mapping) for item in ir.rows):
            issues.append("rows must be a list of objects or null")
            sanitized_ir = ir.model_copy(update={"rows": None})

    # entities.summary must be string or null when present
    entities = getattr(ir, "entities", None)
    if entities is not None and hasattr(entities, "summary"):
        summary_value = getattr(entities, "summary")
        if summary_value is not None and not isinstance(summary_value, str):
            issues.append("entities.summary must be a string or null")

    # No HTML in text
    if _HTML_PATTERN.search(ir.text or ""):
        issues.append("HTML detected in text; stripped")
        sanitized_ir = sanitized_ir.model_copy(update={"text": _strip_html(ir.text)})

    # Detect obvious SQL leakage in text/html fields
    if _SQL_PATTERN.search(ir.text or ""):
        issues.append("SQL detected in text")

    if ir.html and _SQL_PATTERN.search(ir.html):
        issues.append("SQL detected in html")

    # Guard against hallucinated fields by inspecting dump keys
    allowed_keys = {"text", "rows", "html", "entities", "rows_field_present", "version", "task", "decision", "insights"}
    for key in base_dump.keys():
        if key not in allowed_keys:
            issues.append(f"Unexpected field in IR: {key}")

    wrapper = _ValidatedIRWrapper(sanitized_ir, metadata=metadata)
    return {"valid": not issues, "issues": issues, "ir": wrapper, "metadata": metadata}
