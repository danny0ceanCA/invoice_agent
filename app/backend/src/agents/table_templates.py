"""HTML table templates tailored for MV-driven modes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, List

from .ir import AnalyticsIR

# Canonical mode aliases: normalize LLM/router naming drift
MODE_ALIASES: dict[str, str] = {
    # Student monthly variations
    "student_monthly": "student_monthly",
    "student_monthly_spend": "student_monthly",
    "student_monthly_hours": "student_monthly",
    "student_monthly_cost": "student_monthly",

    # Provider monthly variations
    "provider_monthly": "provider_monthly",
    "provider_monthly_hours": "provider_monthly",
    "provider_monthly_spend": "provider_monthly",

    # District monthly variations
    "district_monthly": "district_monthly",
    "district_monthly_spend": "district_monthly",
    "district_monthly_hours": "district_monthly",

    # Student → provider breakdown variations
    "student_provider_breakdown": "student_provider_breakdown",
    "student_provider_year": "student_provider_breakdown",

    # Invoice detail variations
    "invoice_details": "invoice_details",
    "student_invoices": "invoice_details",

    # Service code variations
    "district_service_code_monthly": "district_service_code_monthly",
    "student_service_code_monthly": "student_service_code_monthly",
    "provider_service_code_monthly": "provider_service_code_monthly",

    # Lists
    "student_list": "student_list",
    "clinician_list": "clinician_list",

    # Other modes retained for completeness
    "top_invoices": "top_invoices",
    "provider_caseload_monthly": "provider_caseload_monthly",
    "clinician_student_breakdown": "clinician_student_breakdown",
    "student_daily": "student_daily",
    "provider_daily": "provider_daily",
    "district_daily": "district_daily",
    "student_year_summary": "student_year_summary",
    "student_service_intensity_monthly": "student_service_intensity_monthly",
}


def _utils():
    from . import thin_ir_rendering as tir

    return tir


def _class_for_column(col: str) -> str:
    return _utils()._class_for_column(col)


def _escape_html(value: Any) -> str:
    return _utils()._escape_html(value)


def _format_date(value: Any) -> str:
    return _utils()._format_date(value)


def _format_value(value: Any) -> str:
    return _utils()._format_value(value)


def _is_numeric(value: Any) -> bool:
    return _utils()._is_numeric(value)


def _safe_rows(ir: AnalyticsIR) -> list[dict[str, Any]]:
    rows = ir.rows or []
    if rows and isinstance(rows[0], dict):
        return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _month_sort_key(value: Any) -> tuple:
    if isinstance(value, datetime):
        return (value.year, value.month)

    text = str(value or "")
    for fmt in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%B %Y", "%Y%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            return (parsed.year, parsed.month)
        except (ValueError, TypeError):
            continue
    return (9999, text)


def _format_month(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %Y")

    text = str(value or "")
    for fmt in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%B %Y", "%Y%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%b %Y")
        except (ValueError, TypeError):
            continue
    return text


# -------- NEW: parse service_date into datetime --------
def _parse_service_date(value: Any):
    """Turn strings like '9/1/2025' or '2025-09-01' into datetime objects for sorting."""
    if not value:
        return datetime.max
    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%-m/%-d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return datetime.max


def _numeric_value(value: Any) -> float | None:
    if _is_numeric(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _render_cell(col: str, raw: Any, *, max_cost: float | None = None, allow_cost_bar: bool = False) -> str:
    classes: List[str] = []
    base_class = _class_for_column(col)
    if base_class:
        classes.append(base_class)
    if _is_numeric(raw):
        classes.append("numeric-col")

    class_attr = f' class="{" ".join(classes)}"' if classes else ""

    display = raw
    if isinstance(raw, float):
        display = _format_value(raw)
    if "date" in col.lower():
        display = _format_date(raw)

    if allow_cost_bar and col == "total_cost" and _is_numeric(raw) and max_cost:
        max_value = abs(max_cost)
        if max_value > 0:
            percentage = min(100.0, abs(float(raw)) / max_value * 100)
        else:
            percentage = 0.0
        bar_html = f'<div class="bar-bg"><div class="bar-fill" style="width: {percentage:.0f}%"></div></div>'
        cell_content = (
            f'<div class="bar-wrapper">{bar_html}'
            f'<span class="bar-value">{_escape_html(str(display))}</span></div>'
        )
        return f"<td{class_attr}>{cell_content}</td>"

    return f"<td{class_attr}>{_escape_html(str(display))}</td>"


def _build_table(headers: list[str], body_rows: Iterable[str]) -> str:
    header_html = "".join(f"<th>{_escape_html(h)}</th>" for h in headers)
    thead = f"<thead><tr>{header_html}</tr></thead>"
    tbody = f"<tbody>{''.join(body_rows)}</tbody>"
    return (
        '<div class="table-wrapper">'
        '<table class="analytics-table">'
        f"{thead}{tbody}"
        "</table>"
        "</div>"
    )


def table_student_monthly(ir: AnalyticsIR) -> str:
    rows = _safe_rows(ir)
    if not rows:
        return ""

    ordered_rows = sorted(rows, key=lambda r: _month_sort_key(r.get("service_month")))
    headers = ["Month", "Hours", "Cost"]

    cost_values = [
        abs(_numeric_value(row.get("total_cost")) or 0.0) for row in ordered_rows if _numeric_value(row.get("total_cost")) is not None
    ]
    max_cost = max(cost_values) if cost_values else None

    total_hours = sum(_numeric_value(row.get("total_hours")) or 0.0 for row in ordered_rows)
    total_cost = sum(_numeric_value(row.get("total_cost")) or 0.0 for row in ordered_rows)

    body: List[str] = []
    for row in ordered_rows:
        month = _format_month(row.get("service_month"))
        hours = row.get("total_hours", "")
        cost = row.get("total_cost", "")

        cells = [
            _render_cell("service_month", month),
            _render_cell("total_hours", hours),
            _render_cell("total_cost", cost, max_cost=max_cost, allow_cost_bar=True),
        ]
        body.append(f"<tr>{''.join(cells)}</tr>")

    total_cells = [
        _render_cell("service_month", "Total"),
        _render_cell("total_hours", total_hours),
        _render_cell("total_cost", total_cost),
    ]
    body.append(f"<tr class=\"total-row\">{''.join(total_cells)}</tr>")

    return _build_table(headers, body)


def table_provider_breakdown(ir: AnalyticsIR) -> str:
    rows = _safe_rows(ir)
    if not rows:
        return ""

    sorted_rows = sorted(
        rows,
        key=lambda r: (_numeric_value(r.get("total_cost")) or 0.0) * -1,
    )
    headers = ["Provider", "Hours", "Cost"]
    max_cost = max(
        (abs(_numeric_value(row.get("total_cost")) or 0.0) for row in sorted_rows),
        default=0.0,
    )

    total_hours = sum(_numeric_value(row.get("total_hours")) or 0.0 for row in sorted_rows)
    total_cost = sum(_numeric_value(row.get("total_cost")) or 0.0 for row in sorted_rows)

    body: List[str] = []
    for row in sorted_rows:
        cells = [
            _render_cell("provider", row.get("provider", "")),
            _render_cell("total_hours", row.get("total_hours", "")),
            _render_cell(
                "total_cost",
                row.get("total_cost", ""),
                max_cost=max_cost,
                allow_cost_bar=True,
            ),
        ]
        body.append(f"<tr>{''.join(cells)}</tr>")

    total_cells = [
        _render_cell("provider", "Total"),
        _render_cell("total_hours", total_hours),
        _render_cell("total_cost", total_cost),
    ]
    body.append(f"<tr class=\"total-row\">{''.join(total_cells)}</tr>")

    return _build_table(headers, body)


def table_invoice_details(ir: AnalyticsIR) -> str:
    rows = _safe_rows(ir)
    if not rows:
        return ""

    # Sort rows by parsed service_date for correct chronological ordering
    rows = sorted(
        rows,
        key=lambda r: _parse_service_date(r.get("service_date"))
    )

    headers = [
        "Invoice #",
        "Service Date",
        "Clinician",
        "Service Code",
        "Hours",
        "Cost",
    ]

    body: List[str] = []
    for row in rows:
        cells = [
            _render_cell("invoice_number", row.get("invoice_number", "")),
            _render_cell("service_date", row.get("service_date", "")),
            _render_cell("clinician", row.get("clinician", "")),
            _render_cell("service_code", row.get("service_code", "")),
            _render_cell("hours", row.get("hours", "")),
            _render_cell("cost", row.get("cost", "")),
        ]
        body.append(f"<tr>{''.join(cells)}</tr>")

    return _build_table(headers, body)


def table_district_monthly(ir: AnalyticsIR) -> str:
    rows = _safe_rows(ir)
    if not rows:
        return ""

    ordered_rows = sorted(rows, key=lambda r: _month_sort_key(r.get("service_month")))
    headers = ["Month", "Hours", "Cost"]

    cost_values = [
        abs(_numeric_value(row.get("total_cost")) or 0.0) for row in ordered_rows if _numeric_value(row.get("total_cost")) is not None
    ]
    max_cost = max(cost_values) if cost_values else None

    total_hours = sum(_numeric_value(row.get("total_hours")) or 0.0 for row in ordered_rows)
    total_cost = sum(_numeric_value(row.get("total_cost")) or 0.0 for row in ordered_rows)

    body: List[str] = []
    for row in ordered_rows:
        cells = [
            _render_cell("service_month", _format_month(row.get("service_month"))),
            _render_cell("total_hours", row.get("total_hours", "")),
            _render_cell(
                "total_cost",
                row.get("total_cost", ""),
                max_cost=max_cost,
                allow_cost_bar=True,
            ),
        ]
        body.append(f"<tr>{''.join(cells)}</tr>")

    total_cells = [
        _render_cell("service_month", "Total"),
        _render_cell("total_hours", total_hours),
        _render_cell("total_cost", total_cost),
    ]
    body.append(f"<tr class=\"total-row\">{''.join(total_cells)}</tr>")

    return _build_table(headers, body)


def table_service_code_monthly(ir: AnalyticsIR) -> str:
    rows = _safe_rows(ir)
    if not rows:
        return ""

    headers = ["Service Code", "Month", "Hours", "Cost"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        code = str(row.get("service_code", ""))
        grouped.setdefault(code, []).append(row)

    body: List[str] = []
    total_hours = 0.0
    total_cost = 0.0

    for code in sorted(grouped.keys()):
        group_rows = sorted(grouped[code], key=lambda r: _month_sort_key(r.get("service_month")))
        body.append(
            f'<tr class="group-row"><td colspan="4">{_escape_html(code or "Service Code")}</td></tr>'
        )
        for row in group_rows:
            hours_val = row.get("total_hours", "")
            cost_val = row.get("total_cost", "")
            total_hours += _numeric_value(hours_val) or 0.0
            total_cost += _numeric_value(cost_val) or 0.0
            cells = [
                _render_cell("service_code", code),
                _render_cell("service_month", _format_month(row.get("service_month"))),
                _render_cell("total_hours", hours_val),
                _render_cell("total_cost", cost_val),
            ]
            body.append(f"<tr>{''.join(cells)}</tr>")

    if body:
        total_cells = [
            _render_cell("service_code", "Total"),
            _render_cell("service_month", ""),
            _render_cell("total_hours", total_hours),
            _render_cell("total_cost", total_cost),
        ]
        body.append(f"<tr class=\"total-row\">{''.join(total_cells)}</tr>")

    return _build_table(headers, body)


def table_generic(ir: AnalyticsIR) -> str:
    from .thin_ir_rendering import build_html_table

    return build_html_table(ir)


TEMPLATE_MAP: dict[str, Callable[[AnalyticsIR], str]] = {
    "student_monthly": table_student_monthly,
    "student_provider_breakdown": table_provider_breakdown,
    "invoice_details": table_invoice_details,
    "district_monthly": table_district_monthly,
    "district_service_code_monthly": table_service_code_monthly,
}


def select_table_template(ir: AnalyticsIR, mode: str | None) -> str:
    """
    Return HTML string for the table based on router mode.
    """

    # Normalize mode using MODE_ALIASES
    canonical_mode = MODE_ALIASES.get(mode, mode) if mode else None

    # Store canonical mode back on IR for consistent downstream access
    if canonical_mode:
        setattr(ir, "mode", canonical_mode)

    template = TEMPLATE_MAP.get(canonical_mode) if canonical_mode else None
    if template is None:
        return table_generic(ir)

    try:
        return template(ir)
    except Exception:
        return table_generic(ir)
