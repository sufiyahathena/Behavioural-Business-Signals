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
    "app_rating",
    "youtube_subscribers",
    "instagram_followers",
    "tiktok_total_likes",
    "glassdoor_overall",
    "glassdoor_ceo_approval",
    "glassdoor_recommend",
]

# Bucket membership — used for completeness tracking
CONSUMER_METRICS = ["trustpilot_rating", "app_rating"]
EMPLOYEE_METRICS = ["glassdoor_overall", "glassdoor_ceo_approval", "glassdoor_recommend"]
MOMENTUM_METRICS = [
    "google_trends_score_us", "google_trends_score_global",
    "youtube_subscribers", "instagram_followers", "tiktok_total_likes",
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
        "youtube.csv":  ["youtube_subscribers"],
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


def _get_weights(ticker: str, metrics: set, trustpilot_reviews, geography: dict) -> dict:
    """Calculate per-company weights with missing-data redistribution within each bucket.

    Returns a dict of metric -> weight where all weights sum to 100.

    Args:
        ticker: Company ticker symbol.
        metrics: Set of metric names with valid (non-NaN) normalised values.
        trustpilot_reviews: Raw Trustpilot review count, or None if unavailable.
        geography: Full COMPANY_GEOGRAPHY mapping dict.
    """
    # Consumer bucket
    if trustpilot_reviews is not None and trustpilot_reviews >= config.TRUSTPILOT_CONFIDENCE_THRESHOLD:
        w_tp = 10
        w_app = 12
    else:
        w_tp = 6
        w_app = 16

    # Employee bucket
    w_gd_overall   = 10
    w_gd_ceo       = 8
    w_gd_recommend = 12

    # Momentum bucket — geography-dependent Trends split
    geo = geography.get(ticker, "mixed")
    if geo == "us":
        w_trends_us = 15; w_trends_global = 0
    elif geo == "global":
        w_trends_us = 0;  w_trends_global = 15
    else:
        w_trends_us = 7.5; w_trends_global = 7.5

    w_youtube   = 9
    w_instagram = 13
    w_tiktok    = 11

    # Build each bucket from available metrics only
    consumer: dict = {}
    if "trustpilot_rating" in metrics:
        consumer["trustpilot_rating"] = w_tp
    if "app_rating" in metrics:
        consumer["app_rating"] = w_app

    # Consumer collapse: app missing + low-confidence Trustpilot → redistribute consumer
    # weight proportionally to Employee and Momentum rather than piling onto weak signal
    consumer_collapse = (
        "app_rating" not in metrics and
        (trustpilot_reviews is None or trustpilot_reviews < config.TRUSTPILOT_CONFIDENCE_THRESHOLD)
    )
    missing_consumer = (w_tp + w_app) - sum(consumer.values())

    employee: dict = {}
    if "glassdoor_overall" in metrics:
        employee["glassdoor_overall"] = w_gd_overall
    if "glassdoor_ceo_approval" in metrics:
        employee["glassdoor_ceo_approval"] = w_gd_ceo
    if "glassdoor_recommend" in metrics:
        employee["glassdoor_recommend"] = w_gd_recommend

    if len(employee) < 3 and employee:
        missing_emp = sum([w_gd_overall, w_gd_ceo, w_gd_recommend]) - sum(employee.values())
        emp_per = missing_emp / len(employee)
        employee = {k: v + emp_per for k, v in employee.items()}

    momentum: dict = {}
    if "google_trends_score_us" in metrics and w_trends_us > 0:
        momentum["google_trends_score_us"] = w_trends_us
    if "google_trends_score_global" in metrics and w_trends_global > 0:
        momentum["google_trends_score_global"] = w_trends_global
    if "youtube_subscribers" in metrics:
        momentum["youtube_subscribers"] = w_youtube
    if "instagram_followers" in metrics:
        momentum["instagram_followers"] = w_instagram
    if "tiktok_total_likes" in metrics:
        momentum["tiktok_total_likes"] = w_tiktok

    base_momentum_total = w_trends_us + w_trends_global + w_youtube + w_instagram + w_tiktok
    momentum_missing = base_momentum_total - sum(momentum.values())
    if momentum_missing > 0 and momentum:
        per = momentum_missing / len(momentum)
        momentum = {k: v + per for k, v in momentum.items()}

    if consumer_collapse and missing_consumer > 0:
        emp_total = sum(employee.values())
        mom_total = sum(momentum.values())
        combined = emp_total + mom_total
        if combined > 0:
            emp_per = missing_consumer * (emp_total / combined) / len(employee) if employee else 0
            mom_per = missing_consumer * (mom_total / combined) / len(momentum) if momentum else 0
            employee = {k: v + emp_per for k, v in employee.items()}
            momentum = {k: v + mom_per for k, v in momentum.items()}

    all_weights = {**consumer, **employee, **momentum}
    total = sum(all_weights.values())
    if total > 0:
        all_weights = {k: v / total * 100 for k, v in all_weights.items()}

    return all_weights


def compute_behavioural_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted behavioural scores using per-company dynamic weights.

    Each company gets weights based on:
    - Geography (US/global/mixed) for Google Trends
    - Trustpilot review count for Consumer bucket confidence
    - Missing metrics redistributed equally within their bucket only

    Args:
        df: DataFrame with one row per company containing raw behavioural metrics.

    Returns:
        DataFrame with normalised metric columns and behavioural_score (0-100).
    """
    df = df.copy()

    # ── Step 1: Normalise each metric across all companies ────────────
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

    # ── Step 2: Score each company ────────────────────────────────────
    scores = []
    completeness_list = []
    missing_list = []

    for i, row in df.iterrows():
        ticker = row.get("ticker", "")

        available = {
            m for m in BEHAVIOURAL_METRICS
            if pd.notna(row.get(f"{m}_norm"))
        }
        missing = [m for m in BEHAVIOURAL_METRICS if m not in available]

        if not available:
            scores.append(np.nan)
            completeness_list.append(f"0/{len(BEHAVIOURAL_METRICS)}")
            missing_list.append(", ".join(BEHAVIOURAL_METRICS))
            continue

        trustpilot_count = row.get("trustpilot_review_count", np.nan)
        try:
            review_count = float(trustpilot_count) if pd.notna(trustpilot_count) else None
        except (ValueError, TypeError):
            review_count = None

        weights = _get_weights(ticker, available, review_count, config.COMPANY_GEOGRAPHY)

        weighted_score = sum(
            row[f"{m}_norm"] * weights.get(m, 0.0)
            for m in available
            if weights.get(m, 0.0) > 0
        )

        scores.append(round(weighted_score, 2))
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

    logger.info("Loading social media data")
    social_path = Path(behavioural_dir) / "social_manual.csv"
    if social_path.exists():
        social_df = pd.read_csv(social_path).rename(columns={
            "ig_followers":   "instagram_followers",
            "tt_total_likes": "tiktok_total_likes",
        })[["ticker", "instagram_followers", "tiktok_total_likes"]]
    else:
        logger.warning("social_manual.csv not found at %s — social metrics skipped", social_path)
        social_df = pd.DataFrame()

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

    if not social_df.empty:
        if df.empty:
            df = social_df
        else:
            df = df.merge(social_df, on="ticker", how="left")

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
