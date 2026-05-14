"""Behavioural Business Quality Scorer.

Loads consumer, employee, and market-attention signals from data/behavioural/,
normalises each metric, applies configured weights, and produces a 0–100
behavioural_score per company. Output is saved to data/scores/behavioural_scores.csv.
"""

import logging
from pathlib import Path
from datetime import date

import pandas as pd
import numpy as np

import config
from processors.normaliser import normalise_dataframe

logger = logging.getLogger(__name__)

BEHAVIOURAL_METRICS = [
    "google_trends_score_us",
    "google_trends_score_global",
    "trustpilot_rating",
    "trustpilot_review_count",
    "app_rating",
    "reddit_sentiment",
    "glassdoor_overall",
    "glassdoor_ceo_approval",
    "glassdoor_recommend",
]

GLASSDOOR_COL_MAP = {
    "overall_rating": "glassdoor_overall",
    "ceo_approval_pct": "glassdoor_ceo_approval",
    "recommend_to_friend_pct": "glassdoor_recommend",
}


def load_glassdoor(behavioural_dir: str = config.BEHAVIOURAL_DIR) -> pd.DataFrame:
    """Load and clean the manually-maintained Glassdoor CSV.

    Args:
        behavioural_dir: Directory containing glassdoor_manual.csv.

    Returns:
        DataFrame with ticker, company_name, and standardised Glassdoor columns.
    """
    path = Path(behavioural_dir) / "glassdoor_manual.csv"
    if not path.exists():
        logger.warning("glassdoor_manual.csv not found at %s", path)
        return pd.DataFrame()

    df = pd.read_csv(path)
    df = df.rename(columns=GLASSDOOR_COL_MAP)

    # Convert percentage columns to 0–1 scale before normalisation
    for pct_col in ["glassdoor_ceo_approval", "glassdoor_recommend"]:
        if pct_col in df.columns:
            df[pct_col] = df[pct_col] / 100.0

    # Replace 0.0 placeholders (unfilled) with NaN so median fallback triggers
    for col in GLASSDOOR_COL_MAP.values():
        if col in df.columns:
            df[col] = df[col].replace(0.0, np.nan)

    return df[["ticker", "company_name"] + list(GLASSDOOR_COL_MAP.values())]


def load_collector_outputs(behavioural_dir: str = config.BEHAVIOURAL_DIR) -> pd.DataFrame:
    """Load all collector output CSVs from the behavioural data directory.

    Expects files named: trends.csv, trustpilot.csv, appstore.csv, reddit.csv.
    Missing files are skipped gracefully.

    Args:
        behavioural_dir: Directory containing collector output CSVs.

    Returns:
        Merged DataFrame keyed on ticker. Empty columns added for any missing sources.
    """
    data_path = Path(behavioural_dir)
    collector_files = {
        "trends.csv": ["google_trends_score_us", "google_trends_score_global"],
        "trustpilot.csv": ["trustpilot_rating", "trustpilot_review_count"],
        "appstore.csv": ["app_rating"],
        "reddit.csv": ["reddit_sentiment"],
    }

    merged: pd.DataFrame | None = None

    for filename, expected_cols in collector_files.items():
        file_path = data_path / filename
        if not file_path.exists():
            logger.warning("Collector output not found: %s — will use median fallback", filename)
            continue

        df = pd.read_csv(file_path)
        if "ticker" not in df.columns:
            logger.warning("Skipping %s: missing 'ticker' column", filename)
            continue

        cols_to_keep = ["ticker"] + [c for c in expected_cols if c in df.columns]
        df = df[cols_to_keep]

        if merged is None:
            merged = df
        else:
            merged = merged.merge(df, on="ticker", how="outer")

    return merged if merged is not None else pd.DataFrame()


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
            if pd.isna(median_val):
                median_val = 0.0
            logger.warning(
                "Column '%s': %d missing values filled with median (%.4f)",
                col, n_missing, median_val,
            )
            result[col] = result[col].fillna(median_val)
    return result


def compute_behavioural_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted behavioural scores for all companies.

    Args:
        df: DataFrame with one row per company containing raw behavioural metrics.

    Returns:
        DataFrame with original columns plus normalised metric columns and
        behavioural_score (0–100).
    """
    df = _fill_missing_with_median(df, BEHAVIOURAL_METRICS)
    df = normalise_dataframe(df, BEHAVIOURAL_METRICS)

    score = pd.Series(0.0, index=df.index)
    for metric, weight in config.BEHAVIOURAL_WEIGHTS.items():
        norm_col = f"{metric}_norm"
        if norm_col in df.columns:
            score += df[norm_col] * weight

    df["behavioural_score"] = (score * 100).round(2)
    return df


def run(
    behavioural_dir: str = config.BEHAVIOURAL_DIR,
    scores_dir: str = config.SCORES_DIR,
) -> pd.DataFrame:
    """Load behavioural signals, score all companies, and save results.

    Args:
        behavioural_dir: Directory containing Glassdoor CSV and collector outputs.
        scores_dir: Directory where the scored output CSV will be written.

    Returns:
        Scored DataFrame with behavioural_score column.
    """
    logger.info("Loading Glassdoor data")
    glassdoor_df = load_glassdoor(behavioural_dir)

    logger.info("Loading collector outputs from %s", behavioural_dir)
    collector_df = load_collector_outputs(behavioural_dir)

    if glassdoor_df.empty and collector_df.empty:
        logger.error("No behavioural data found — cannot compute scores.")
        return pd.DataFrame()

    # Merge Glassdoor with collector outputs
    if glassdoor_df.empty:
        df = collector_df
    elif collector_df.empty:
        df = glassdoor_df
    else:
        df = glassdoor_df.merge(collector_df, on="ticker", how="outer")

    logger.info("Scoring %d companies", len(df))
    df = compute_behavioural_scores(df)

    output_path = Path(scores_dir) / "behavioural_scores.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df["last_updated"] = date.today().isoformat()
    df.to_csv(output_path, index=False)
    print(f"Behavioural scores saved to {output_path}")
    logger.info("Behavioural scores saved to %s", output_path)

    return df
