"""Thin IR reducer and HTML helpers for the rendering model."""

from __future__ import annotations

from typing import Any, Dict, List

from .ir import AnalyticsIR


def _extract_entities(ir: AnalyticsIR) -> Dict[str, List[str]]:
    """Return minimal entity context from the IR."""

    entities = {"students": [], "providers": [], "vendors": []}
    if ir.entities is None:
        return entities

    entities["students"] = list(ir.entities.students)
    entities["providers"] = list(ir.entities.providers)
    entities["vendors"] = list(ir.entities.vendors)
    return entities


def reduce_ir_for_rendering(ir: AnalyticsIR, insights: List[str] | None = None) -> dict:
    """
    Reduce the IR to a thin form for the rendering model.

    The goal is to give the LLM just enough context to write a good
    summary and follow-up suggestion, without sending full row-level
    data or the entire IR JSON.
    """

    rows = ir.rows or []
    has_rows = bool(rows)

    columns: List[str] = []
    if rows and isinstance(rows[0], dict):
        columns = list(rows[0].keys())

    row_count = len(rows)

    # Basic numeric summaries for a handful of columns (if present)
    numeric_summaries: Dict[str, Dict[str, float]] = {}
    if rows and isinstance(rows[0], dict):
        first_row = rows[0]
        candidate_numeric_cols = [
            key
            for key, value in first_row.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]

        for col in candidate_numeric_cols:
            values: List[float] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                v = row.get(col)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    values.append(float(v))
            if values:
                numeric_summaries[col] = {
                    "sum": float(sum(values)),
                    "min": float(min(values)),
                    "max": float(max(values)),
                }

    return {
        "has_rows": has_rows,
        "row_count": row_count,
        "columns": columns,
        "numeric_summaries": numeric_summaries,
        "entities": _extract_entities(ir),
        "insights": list(insights or []),
    }


def _escape_html(value: Any) -> str:
    """Minimal HTML escaping for cell content."""

    if value is None:
        text = ""
    else:
        text = str(value)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ============================
# Formatting Utilities
# ============================

def _format_value(value: Any) -> str:
    """Format numeric values to 2 decimals; leave others alone."""
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _format_date(value: Any) -> str:
    """Convert timestamp or datetime string to YYYY-MM-DD."""
    if not value:
        return ""
    text = str(value)
    # Remove time if present
    if "T" in text:
        return text.split("T")[0]
    return text.split(" ")[0]


def _class_for_column(col: str) -> str:
    """Return semantic class name for CSS based on column content."""
    col_lower = col.lower()
    if any(k in col_lower for k in ["cost", "amount", "spend"]):
        return "amount-col"
    if "hour" in col_lower:
        return "hours-col"
    if "date" in col_lower:
        return "date-col"
    return ""


# ============================
# HTML TABLE BUILDER
# ============================

def build_html_table(ir: AnalyticsIR) -> str:
    """
    Build a deterministic HTML table from IR.rows.

    This keeps the LLM from having to recreate row-level HTML and
    ensures consistent structure across responses.
    """

    rows = ir.rows or []
    if not rows or not isinstance(rows[0], dict):
        return ""

    columns: List[str] = list(rows[0].keys())

    # ---------- HEADER ----------
    header_cells = "".join(
        f"<th>{_escape_html(col.replace('_', ' ').title())}</th>"
        for col in columns
    )
    thead = f"<thead><tr>{header_cells}</tr></thead>"

    # ---------- BODY ----------
    body_rows: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cell_html_list = []
        for col in columns:
            raw = row.get(col, "")
            display = raw

            # Format numeric
            if isinstance(raw, float):
                display = _format_value(raw)

            # Format dates
            if "date" in col.lower():
                display = _format_date(raw)

            css_class = _class_for_column(col)
            class_attr = f' class="{css_class}"' if css_class else ""

            cell_html_list.append(
                f"<td{class_attr}>{_escape_html(display)}</td>"
            )

        cells = "".join(cell_html_list)
        body_rows.append(f"<tr>{cells}</tr>")

    tbody = f"<tbody>{''.join(body_rows)}</tbody>"

    return (
        '<div class="table-wrapper">'
        '<table class="analytics-table">'
        f"{thead}{tbody}"
        "</table>"
        "</div>"
    )
