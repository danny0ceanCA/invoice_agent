"""Thin IR reducer and HTML helpers for the rendering model."""

from __future__ import annotations

from datetime import datetime
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
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            ts_value = float(value)
            if ts_value > 1e12:
                ts_value = ts_value / 1000
            return datetime.utcfromtimestamp(ts_value).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            pass
    text = str(value)
    # Remove time if present
    if "T" in text:
        return text.split("T")[0]
    return text.split(" ")[0]


def _is_numeric(value: Any) -> bool:
    """Return True for int/float but not bool."""

    return isinstance(value, (int, float)) and not isinstance(value, bool)


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

    # Detect numeric columns and pre-compute totals / maxima
    numeric_columns = set()
    col_totals: Dict[str, float] = {}
    col_max_values: Dict[str, float] = {}

    for col in columns:
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_value = row.get(col)
            if _is_numeric(raw_value):
                numeric_columns.add(col)
                col_totals.setdefault(col, 0.0)
                col_max_values.setdefault(col, 0.0)
                break

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
            classes = []

            # Format numeric
            if isinstance(raw, float):
                display = _format_value(raw)

            # Format dates
            if "date" in col.lower():
                display = _format_date(raw)

            # Track totals and maxima
            if col in numeric_columns and _is_numeric(raw):
                numeric_value = float(raw)
                col_totals[col] = col_totals.get(col, 0.0) + numeric_value
                current_max = col_max_values.get(col, 0.0)
                col_max_values[col] = max(current_max, abs(numeric_value))

            base_class = _class_for_column(col)
            if base_class:
                classes.append(base_class)

            if col in numeric_columns:
                classes.append("numeric-col")

            # Cost color coding
            if base_class == "amount-col" and _is_numeric(raw):
                numeric_value = float(raw)
                if numeric_value > 7000:
                    classes.append("high-cost")
                elif numeric_value > 4000:
                    classes.append("med-cost")
                else:
                    classes.append("low-cost")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""

            cell_content = _escape_html(display)

            if col in numeric_columns:
                max_value = col_max_values.get(col, 0.0)
                percentage = 0.0
                if max_value > 0 and _is_numeric(raw):
                    percentage = min(100.0, abs(float(raw)) / max_value * 100)
                bar_html = (
                    f'<div class="bar-bg"><div class="bar-fill" style="width: {percentage:.0f}%"></div></div>'
                )
                cell_content = (
                    f'<div class="bar-wrapper">{bar_html}'
                    f'<span class="bar-value">{_escape_html(display)}</span></div>'
                )

            cell_html_list.append(f"<td{class_attr}>{cell_content}</td>")

        cells = "".join(cell_html_list)
        body_rows.append(f"<tr>{cells}</tr>")

    # ---------- TOTALS ROW ----------
    if numeric_columns:
        total_cells: List[str] = []
        for idx, col in enumerate(columns):
            classes = []
            base_class = _class_for_column(col)
            if base_class:
                classes.append(base_class)
            if col in numeric_columns:
                classes.append("numeric-col")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""

            if idx == 0:
                total_cells.append(f"<td{class_attr}>Total</td>")
                continue

            if col in numeric_columns:
                total_value = col_totals.get(col, 0.0)
                display = _format_value(float(total_value))
                total_cells.append(
                    f"<td{class_attr}>{_escape_html(display)}</td>"
                )
            else:
                total_cells.append(f"<td{class_attr}></td>")

        body_rows.append(f"<tr class=\"total-row\">{''.join(total_cells)}</tr>")

    tbody = f"<tbody>{''.join(body_rows)}</tbody>"

    return (
        '<div class="table-wrapper">'
        '<table class="analytics-table">'
        f"{thead}{tbody}"
        "</table>"
        "</div>"
    )
