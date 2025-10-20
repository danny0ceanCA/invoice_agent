"""Data cleaning service."""

from __future__ import annotations

import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Perform lightweight cleaning on a dataframe."""
    cleaned = df.copy()
    cleaned.columns = [column.strip() for column in cleaned.columns]
    return cleaned
