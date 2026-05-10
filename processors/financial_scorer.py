"""Financial Health and Performance Scorer.

Loads raw financial metrics from data/financial/, normalises each metric,
applies configured weights, and produces a 0–100 financial_score per company.
Output is saved to data/scores/financial_scores.csv.
"""

import logging
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np

import config
from processors.normaliser import normalise_dataframe

logger = logging.getLogger(__name__)

FINANCIAL_METRICS = [
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_profit_margin",
    "fcf_margin",
    "debt_to_equity",
    "current_ratio",
    "roe",
    "roa",
    "interest_coverage",
]

INVERT_METRICS = ["debt_to_equity"]


def load_financial_data(financial_dir: str = config.FINANCIAL_DIR) -> pd.DataFrame:
    """Load and merge all CSV files from the financial data directory.

    Args:
        financial_dir: Path to the directory containing raw financial CSVs.

    Returns:
        Merged DataFrame with one row per ticker. Returns empty DataFrame if no
        files are found.
    """
    data_path = Path(financial_dir)
    csv_files = list(data_path.glob("*.csv"))

    if not csv_files:
        logger.warning("No CSV files found in %s", financial_dir)
        return pd.DataFrame()

    frames = [pd.read_csv(f) for f in csv_files]
    df = pd.concat(frames, ignore_index=True)

    if "ticker" in df.columns:
        df = df.drop_duplicates(subset="ticker", keep="last")

    return df


def _fill_missing_with_median(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    """Fill NaN values in specified columns with the column median.

    Logs a warning for each column where imputation is applied.

    Args:
        df: DataFrame potentially containing NaN values.
        columns: List of column names to check and fill.

    Returns:
        DataFrame with NaN values replaced by column medians.
    """
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            result[col] = np.nan
        n_missing = result[col].isna().sum()
        if n_missing > 0:
            median_val = result[col].median()
            logger.warning(
                "Column '%s': %d missing values filled with median (%.4f)",
                col, n_missing, median_val,
            )
            result[col] = result[col].fillna(median_val)
    return result


def compute_financial_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted financial scores for all companies.

    Args:
        df: DataFrame with one row per company containing raw financial metrics.

    Returns:
        DataFrame with original columns plus normalised metric columns and
        financial_score (0–100).
    """
    df = _fill_missing_with_median(df, FINANCIAL_METRICS)
    df = normalise_dataframe(df, FINANCIAL_METRICS, invert_cols=INVERT_METRICS)

    score = pd.Series(0.0, index=df.index)
    for metric, weight in config.FINANCIAL_WEIGHTS.items():
        norm_col = f"{metric}_norm"
        if norm_col in df.columns:
            score += df[norm_col] * weight

    df["financial_score"] = (score * 100).round(2)
    return df


def run(
    financial_dir: str = config.FINANCIAL_DIR,
    scores_dir: str = config.SCORES_DIR,
) -> pd.DataFrame:
    """Load financial data, score all companies, and save results.

    Args:
        financial_dir: Directory containing raw financial CSV files.
        scores_dir: Directory where the scored output CSV will be written.

    Returns:
        Scored DataFrame with financial_score column.
    """
    logger.info("Loading financial data from %s", financial_dir)
    df = load_financial_data(financial_dir)

    if df.empty:
        logger.error("No financial data found — cannot compute scores.")
        return df

    logger.info("Scoring %d companies", len(df))
    df = compute_financial_scores(df)

    output_path = Path(scores_dir) / "financial_scores.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df["last_updated"] = date.today().isoformat()
    df.to_csv(output_path, index=False)
    print(f"Financial scores saved to {output_path}")
    logger.info("Financial scores saved to %s", output_path)

    return df
