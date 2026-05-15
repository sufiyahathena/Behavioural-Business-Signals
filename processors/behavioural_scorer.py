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
    "glassdoor_overall",
    "glassdoor_ceo_approval",
    "glassdoor_recommend",
]

# Bucket membership — used for intra-bucket weight redistribution
CONSUMER_METRICS = ["trustpilot_rating", "app_rating"]
EMPLOYEE_METRICS = ["glassdoor_overall", "glassdoor_ceo_approval", "glassdoor_recommend"]
MOMENTUM_METRICS = ["google_trends_score_us", "google_trends_score_global", "youtube_subscribers"]

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


def _build_company_weights(ticker: str, trustpilot_review_count) -> dict:
    """Build per-company metric weights based on geography and Trustpilot confidence.

    Rules:
    - Consumer bucket: Trustpilot weight depends on review count (>=100 = high confidence)
    - Employee bucket: fixed weights always
    - Momentum bucket: Google Trends weights depend on company geography
    - Missing metrics: weight redistributed equally within same bucket only

    Args:
        ticker: Company ticker symbol.
        trustpilot_review_count: Raw review count from data (float or NaN).

    Returns:
        Dict of metric -> weight (all weights sum to 1.0 across available metrics).
    """
    # ── Consumer bucket weights ───────────────────────────────────────
    try:
        review_count = float(trustpilot_review_count)
        high_confidence = pd.notna(review_count) and review_count >= config.TRUSTPILOT_CONFIDENCE_THRESHOLD
    except (ValueError, TypeError):
        high_confidence = False

    consumer_weights = dict(
        config.CONSUMER_WEIGHTS_HIGH_CONFIDENCE if high_confidence
        else config.CONSUMER_WEIGHTS_LOW_CONFIDENCE
    )

    # ── Employee bucket weights ───────────────────────────────────────
    employee_weights = dict(config.EMPLOYEE_WEIGHTS)

    # ── Momentum bucket weights ───────────────────────────────────────
    geo = config.COMPANY_GEOGRAPHY.get(ticker, "mixed")
    if geo == "us":
        momentum_weights = dict(config.MOMENTUM_WEIGHTS_US)
    elif geo == "global":
        momentum_weights = dict(config.MOMENTUM_WEIGHTS_GLOBAL)
    else:
        momentum_weights = dict(config.MOMENTUM_WEIGHTS_MIXED)

    # Apply proxy discount to YouTube if company uses a subsidiary channel
    if ticker in config.YOUTUBE_PROXY_TICKERS:
        momentum_weights["youtube_subscribers"] = (
            momentum_weights["youtube_subscribers"] * config.YOUTUBE_PROXY_DISCOUNT
        )

    return {**consumer_weights, **employee_weights, **momentum_weights}


def _redistribute_within_bucket(
    weights: dict,
    bucket_metrics: list,
    available_metrics: set,
) -> dict:
    """Redistribute missing metric weights equally within the same bucket.

    If a metric is missing (not in available_metrics), its weight is split
    equally across the other available metrics in the same bucket.
    Other buckets are not affected.

    Args:
        weights: Current weight dict for all metrics.
        bucket_metrics: All metrics belonging to this bucket.
        available_metrics: Set of metrics that have real data for this company.

    Returns:
        Updated weights dict with redistributed weights within this bucket.
    """
    weights = dict(weights)

    bucket_available = [m for m in bucket_metrics if m in available_metrics]
    bucket_missing   = [m for m in bucket_metrics if m not in available_metrics]

    for missing in bucket_missing:
        missing_weight = weights.get(missing, 0.0)
        if missing_weight == 0.0 or not bucket_available:
            weights[missing] = 0.0
            continue
        share = missing_weight / len(bucket_available)
        for m in bucket_available:
            weights[m] = weights.get(m, 0.0) + share
        weights[missing] = 0.0

    return weights


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
        weights = _build_company_weights(ticker, trustpilot_count)

        # ── Special case: low-confidence Trustpilot + missing App Rating ──
        # If both conditions are true, do not let the missing App Rating weight
        # collapse onto a weak Trustpilot signal. Instead redistribute the
        # App Rating weight proportionally across Employee and Momentum buckets.
        try:
            review_count = float(trustpilot_count) if pd.notna(trustpilot_count) else 0
        except (ValueError, TypeError):
            review_count = 0

        app_missing = "app_rating" not in available
        low_confidence = review_count < config.TRUSTPILOT_CONFIDENCE_THRESHOLD

        if app_missing and low_confidence:
            app_weight = weights.get("app_rating", 0.0)
            weights["app_rating"] = 0.0

            # Redistribute app_weight proportionally across Employee and Momentum
            # Employee bucket total = 30%, Momentum bucket total = 28%
            employee_share = app_weight * (30 / 58)
            momentum_share = app_weight * (28 / 58)

            available_employee = [m for m in EMPLOYEE_METRICS if m in available]
            if available_employee:
                per_employee = employee_share / len(available_employee)
                for m in available_employee:
                    weights[m] = weights.get(m, 0.0) + per_employee

            available_momentum = [m for m in MOMENTUM_METRICS if m in available]
            if available_momentum:
                per_momentum = momentum_share / len(available_momentum)
                for m in available_momentum:
                    weights[m] = weights.get(m, 0.0) + per_momentum

            weights = _redistribute_within_bucket(weights, EMPLOYEE_METRICS, available)
            weights = _redistribute_within_bucket(weights, MOMENTUM_METRICS, available)

        else:
            weights = _redistribute_within_bucket(weights, CONSUMER_METRICS, available)
            weights = _redistribute_within_bucket(weights, EMPLOYEE_METRICS, available)
            weights = _redistribute_within_bucket(weights, MOMENTUM_METRICS, available)

        weighted_score = sum(
            row[f"{m}_norm"] * weights.get(m, 0.0)
            for m in available
            if weights.get(m, 0.0) > 0
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
