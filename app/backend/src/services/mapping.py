"""Column mapping service."""

from __future__ import annotations

import pandas as pd


def map_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename dataframe columns according to mapping."""
    return df.rename(columns=mapping)
