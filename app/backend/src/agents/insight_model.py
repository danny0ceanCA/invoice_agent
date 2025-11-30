"""Rule-based insight generation for AnalyticsIR rows."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .ir import AnalyticsIR


def _numeric_columns(rows: list[dict[str, Any]]) -> list[str]:
    numeric_cols: list[str] = []
    for key in rows[0].keys():
        for row in rows:
            value = row.get(key)
            if value is None:
                continue
            try:
                float(value)
                numeric_cols.append(str(key))
                break
            except (TypeError, ValueError):
                break
    return numeric_cols


def _month_index(month: str) -> int:
    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    try:
        return months.index(month.strip().lower())
    except Exception:
        return 99


def _label_from_row(row: dict[str, Any]) -> str | None:
    for key in ["student_name", "clinician", "provider", "vendor", "service_month", "category", "name"]:
        value = row.get(key)
        if value:
            return str(value)
    return None


def run_insight_model(ir: AnalyticsIR) -> dict[str, list[str]]:
    """Generate up to four short, plain-English insights from the IR rows."""

    rows = ir.rows or []
    if not rows:
        return {"insights": []}

    insights: list[str] = []
    numeric_cols = _numeric_columns(rows)

    # Trend insight based on service_month + first numeric column
    if "service_month" in rows[0] and numeric_cols:
        metric = numeric_cols[0]
        try:
            sorted_rows = sorted(rows, key=lambda r: _month_index(str(r.get("service_month", ""))))
            if len(sorted_rows) >= 2:
                first = float(sorted_rows[0].get(metric) or 0)
                last = float(sorted_rows[-1].get(metric) or 0)
                if last > first:
                    insights.append("Recent months are trending upward compared to earlier months.")
                elif last < first:
                    insights.append("Recent months are trending downward compared to earlier months.")
        except Exception:
            pass

    # Concentration insight: top entity by numeric value
    if numeric_cols:
        metric = numeric_cols[0]
        try:
            top_row = max(rows, key=lambda r: float(r.get(metric) or 0))
            label = _label_from_row(top_row)
            if label:
                insights.append(f"{label} shows the highest {metric.replace('_', ' ')} in this set.")
        except Exception:
            pass

    # Count insight for recurring labels
    labels = [_label_from_row(row) for row in rows if _label_from_row(row)]
    if labels:
        counts = Counter(labels)
        common_label, common_count = counts.most_common(1)[0]
        if common_count > 1 and len(rows) > 1:
            insights.append(f"{common_label} appears frequently across the results.")

    # Diversity insight
    if len(rows) > 3:
        insights.append("Results cover multiple entries; focus on the largest values for impact.")

    # Ensure clean, short, non-HTML/SQL statements
    cleaned = []
    for insight in insights:
        plain = str(insight).replace("<", "").replace(">", "")
        cleaned.append(plain)

    return {"insights": cleaned[:4]}
