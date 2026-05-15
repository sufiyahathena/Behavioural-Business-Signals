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

logger = logging.getLogger(__name__)

BEHAVIOURAL_METRICS = [
    "google_trends_score_us",
    "google_trends_score_global",
    "trustpilot_rating",
    "trustpilot_review_count",
    "app_rating",
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


def load_trustpilot(behavioural_dir: str = config.BEHAVIOURAL_DIR) -> pd.DataFrame:
    """Load and clean the manually-maintained Trustpilot CSV.

    Args:
        behavioural_dir: Directory containing trustpilot_manual.csv.

    Returns:
        DataFrame with ticker, trustpilot_rating, trustpilot_review_count.
        Returns empty DataFrame if file not found.
    """
    path = Path(behavioural_dir) / "trustpilot_manual.csv"
    if not path.exists():
        logger.warning("trustpilot_manual.csv not found at %s", path)
        return pd.DataFrame()

    df = pd.read_csv(path)

    # Replace 0.0 placeholders with NaN
    for col in ["trustpilot_rating", "trustpilot_review_count"]:
        if col in df.columns:
            df[col] = df[col].replace(0.0, np.nan)

    keep_cols = ["ticker"] + [c for c in ["trustpilot_rating", "trustpilot_review_count"] if c in df.columns]
    return df[keep_cols]


def load_collector_outputs(behavioural_dir: str = config.BEHAVIOURAL_DIR) -> pd.DataFrame:
    """Load all collector output CSVs from the behavioural data directory.

    Expects files named: trends.csv, reddit.csv.
    Missing files are skipped gracefully.

    Args:
        behavioural_dir: Directory containing collector output CSVs.

    Returns:
        Merged DataFrame keyed on ticker. Empty columns added for any missing sources.
    """
    data_path = Path(behavioural_dir)
    collector_files = {
        "trends.csv":   ["google_trends_score_us", "google_trends_score_global"],
        "appstore.csv": ["app_rating"],
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


def compute_behavioural_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted behavioural scores for all companies.

    Missing metrics are excluded per company and weights are rebalanced
    proportionally — no median imputation. This mirrors the financial scorer
    approach: companies are not penalised for lacking a metric (e.g. no app),
    they are simply scored on what is genuinely available.

    Args:
        df: DataFrame with one row per company containing raw behavioural metrics.

    Returns:
        DataFrame with normalised metric columns and behavioural_score (0–100).
    """
    df = df.copy()

    # Normalise each metric across all companies (ignoring NaNs)
    for metric in BEHAVIOURAL_METRICS:
        if metric not in df.columns:
            df[metric] = np.nan

        col = df[metric].copy()
        valid = col.dropna()

        if valid.empty or valid.max() == valid.min():
            df[f"{metric}_norm"] = np.nan
            continue

        norm = (col - valid.min()) / (valid.max() - valid.min())
        df[f"{metric}_norm"] = norm.round(3)

    # Score each company using only available metrics with proportional reweighting
    weights = config.BEHAVIOURAL_WEIGHTS
    scores = []
    completeness_list = []
    missing_list = []

    for i, row in df.iterrows():
        available = [
            m for m in BEHAVIOURAL_METRICS
            if pd.notna(row.get(f"{m}_norm"))
        ]
        missing = [
            m for m in BEHAVIOURAL_METRICS
            if pd.isna(row.get(f"{m}_norm", np.nan))
        ]

        if not available:
            scores.append(np.nan)
            completeness_list.append(f"0/{len(BEHAVIOURAL_METRICS)}")
            missing_list.append(", ".join(BEHAVIOURAL_METRICS))
            continue

        total_weight = sum(weights[m] for m in available if m in weights)
        if total_weight == 0:
            scores.append(np.nan)
            completeness_list.append(f"0/{len(BEHAVIOURAL_METRICS)}")
            missing_list.append(", ".join(missing))
            continue

        weighted_score = sum(
            row[f"{m}_norm"] * (weights[m] / total_weight)
            for m in available
            if m in weights
        )

        scores.append(round(weighted_score * 100, 2))
        completeness_list.append(f"{len(available)}/{len(BEHAVIOURAL_METRICS)}")
        missing_list.append(", ".join(missing) if missing else "")

    df["behavioural_score"] = scores
    df["data_completeness"] = completeness_list
    df["missing_metrics"] = missing_list

    # Log companies with missing metrics
    incomplete = df[df["missing_metrics"] != ""]
    if not incomplete.empty:
        logger.warning("Companies with incomplete behavioural data:")
        for _, row in incomplete.iterrows():
            logger.warning(
                "  %s: missing %s — scored on %s metrics",
                row["ticker"], row["missing_metrics"], row["data_completeness"],
            )

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

    logger.info("Loading Trustpilot data")
    trustpilot_df = load_trustpilot(behavioural_dir)

    logger.info("Loading collector outputs from %s", behavioural_dir)
    collector_df = load_collector_outputs(behavioural_dir)

    # Merge all data sources
    df = glassdoor_df if not glassdoor_df.empty else pd.DataFrame()

    if not trustpilot_df.empty:
        if df.empty:
            df = trustpilot_df
        else:
            df = df.merge(trustpilot_df, on="ticker", how="outer")

    if not collector_df.empty:
        if df.empty:
            df = collector_df
        else:
            df = df.merge(collector_df, on="ticker", how="outer")

    if df.empty:
        logger.error("No behavioural data found — cannot compute scores.")
        return pd.DataFrame()

    logger.info("Scoring %d companies", len(df))
    df = compute_behavioural_scores(df)

    output_path = Path(scores_dir) / "behavioural_scores.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df["last_updated"] = date.today().isoformat()
    df.to_csv(output_path, index=False)
    print(f"Behavioural scores saved to {output_path}")
    logger.info("Behavioural scores saved to %s", output_path)

    return df
