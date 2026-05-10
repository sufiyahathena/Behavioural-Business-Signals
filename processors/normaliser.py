"""Min-max normalisation utilities for financial and behavioural metrics."""

import pandas as pd
import numpy as np


def min_max_normalise(series: pd.Series) -> pd.Series:
    """Normalise a pandas Series to the [0, 1] range using min-max scaling.

    Returns a Series of 0.5 values if the range is zero (all values identical).

    Args:
        series: Numeric pandas Series to normalise.

    Returns:
        Series with values scaled to [0, 1].
    """
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - min_val) / (max_val - min_val)


def normalise_dataframe(
    df: pd.DataFrame,
    columns: list,
    invert_cols: list = [],
) -> pd.DataFrame:
    """Normalise specified columns in a DataFrame and add normalised versions.

    Normalised columns are added with a "_norm" suffix. Columns listed in
    invert_cols have their normalised values flipped (1 - value) so that
    lower raw values score higher (e.g. debt_to_equity).

    Args:
        df: Input DataFrame containing the columns to normalise.
        columns: List of column names to normalise.
        invert_cols: Column names where lower raw values should score higher.

    Returns:
        DataFrame with new "<column>_norm" columns appended.
    """
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            continue
        normalised = min_max_normalise(result[col])
        if col in invert_cols:
            normalised = 1 - normalised
        result[f"{col}_norm"] = normalised
    return result
