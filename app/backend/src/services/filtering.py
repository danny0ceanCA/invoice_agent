"""Filtering helpers."""

from __future__ import annotations

import pandas as pd


def drop_zero_hours(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where Hours column equals zero."""
    if "Hours" not in df.columns:
        return df
    return df[df["Hours"] > 0]
