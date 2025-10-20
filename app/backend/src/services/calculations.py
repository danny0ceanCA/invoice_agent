"""Calculation helpers."""

from __future__ import annotations

import pandas as pd


def apply_rate(df: pd.DataFrame, rates: dict[str, float]) -> pd.DataFrame:
    """Apply hourly rate mapping to dataframe."""
    result = df.copy()
    if "Service Code" in result.columns:
        result["Rate"] = result["Service Code"].map(rates).fillna(0)
    return result


def calc_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Compute cost column from hours and rate."""
    result = df.copy()
    if {"Hours", "Rate"}.issubset(result.columns):
        result["Cost"] = result["Hours"] * result["Rate"]
    return result
