"""Thin IR reducer for the insights model."""

from __future__ import annotations

from typing import Any, Dict, List

from .ir import AnalyticsIR


def _extract_entities(ir: AnalyticsIR) -> Dict[str, List[Any]]:
    """Return minimal entity context from the IR."""

    entities = {"students": [], "providers": [], "vendors": []}
    if ir.entities is None:
        return entities

    entities["students"] = list(ir.entities.students)
    entities["providers"] = list(ir.entities.providers)
    entities["vendors"] = list(ir.entities.vendors)
    return entities


def reduce_ir_for_insights(ir: AnalyticsIR) -> dict:
    """
    Reduce the IR to a thin form for the insights model.
    Only numeric lists, category lists, and minimal entity context.
    """

    thin_ir: dict[str, Any] = {
        "numeric": {},
        "categories": {},
        "entities": _extract_entities(ir),
    }

    if not ir.rows:
        return thin_ir

    first_row = ir.rows[0]
    if not isinstance(first_row, dict):
        return thin_ir

    numeric_columns = []
    category_columns = []
    for key, value in first_row.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_columns.append(key)
        elif isinstance(value, (str, bool)):
            category_columns.append(key)

    for column in numeric_columns:
        numbers: list[float | int] = []
        for row in ir.rows or []:
            val = row.get(column) if isinstance(row, dict) else None
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                numbers.append(val)
        thin_ir["numeric"][column] = numbers

    for column in category_columns:
        categories: list[str] = []
        for row in ir.rows or []:
            val = row.get(column) if isinstance(row, dict) else None
            if isinstance(val, bool):
                categories.append(str(val))
            elif isinstance(val, str):
                categories.append(val)
        thin_ir["categories"][column] = categories

    return thin_ir
