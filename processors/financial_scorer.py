"""Financial Health and Performance Scorer.

Loads raw financial metrics from data/financial/, normalises each metric,
applies configured weights, and produces a 0–100 financial_score per company.

Missing metrics are excluded per company and weights are rebalanced
proportionally — no median imputation.

Output is saved to data/scores/financial_scores.csv.
"""

import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

import config

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
    """Load and merge all CSV files from the financial data directory."""
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


def _normalise_column(series: pd.Series) -> pd.Series:
    """Min-max normalise a series to [0, 1], ignoring NaNs."""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - min_val) / (max_val - min_val)


def compute_financial_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Score companies using only available metrics with proportional reweighting.

    No median imputation — each company is scored on whatever real data exists.
    Weights are renormalised to sum to 1.0 across available metrics only.
    """
    df = df.copy()

    # ── Interest coverage special case ───────────────────────────────
    # Debt-light companies (D/E < 0.5) with NaN interest coverage have no
    # meaningful interest burden — assign 25.0 rather than leaving missing.
    if "interest_coverage" in df.columns and "debt_to_equity" in df.columns:
        mask = df["interest_coverage"].isna() & (df["debt_to_equity"] < 0.5)
        df.loc[mask, "interest_coverage"] = 25.0
        if mask.any():
            logger.info(
                "interest_coverage: set to 25.0 for debt-light companies: %s",
                df[mask]["ticker"].tolist(),
            )

    # ── Normalise each metric across all companies ────────────────────
    normalised = pd.DataFrame(index=df.index)
    for metric in FINANCIAL_METRICS:
        if metric not in df.columns:
            normalised[metric] = np.nan
            continue
        norm = _normalise_column(df[metric].copy())
        if metric in INVERT_METRICS:
            norm = 1 - norm
        normalised[metric] = norm

    # ── Score each company using only available metrics ───────────────
    weights = config.FINANCIAL_WEIGHTS
    scores = []
    completeness_list = []
    missing_list = []

    for i, row in normalised.iterrows():
        available = [m for m in FINANCIAL_METRICS if pd.notna(row[m])]
        missing   = [m for m in FINANCIAL_METRICS if pd.isna(row[m])]

        if not available:
            scores.append(np.nan)
            completeness_list.append("0/10")
            missing_list.append(", ".join(FINANCIAL_METRICS))
            continue

        total_weight = sum(weights[m] for m in available)
        weighted_score = sum(
            row[m] * (weights[m] / total_weight) for m in available
        )

        scores.append(round(weighted_score * 100, 2))
        completeness_list.append(f"{len(available)}/10")
        missing_list.append(", ".join(missing) if missing else "")

    df["financial_score"]  = scores
    df["data_completeness"] = completeness_list
    df["missing_metrics"]   = missing_list

    # Add normalised metric values for company detail pages
    for metric in FINANCIAL_METRICS:
        if metric in normalised.columns:
            df[f"norm_{metric}"] = normalised[metric].round(3).values

    # Log any incomplete companies
    incomplete = df[df["missing_metrics"] != ""]
    if not incomplete.empty:
        logger.warning("Companies with incomplete data:")
        for _, row in incomplete.iterrows():
            logger.warning(
                "  %s: missing %s — scored on %s metrics",
                row["ticker"], row["missing_metrics"], row["data_completeness"],
            )
    else:
        logger.info("All companies scored on complete data (10/10 metrics)")

    return df


def run(
    financial_dir: str = config.FINANCIAL_DIR,
    scores_dir: str = config.SCORES_DIR,
) -> pd.DataFrame:
    """Load financial data, score all companies, and save results."""
    logger.info("Loading financial data from %s", financial_dir)
    df = load_financial_data(financial_dir)

    if df.empty:
        logger.error("No financial data found — cannot compute scores.")
        return df

    logger.info("Scoring %d companies", len(df))
    df = compute_financial_scores(df)

    df = df.sort_values("financial_score", ascending=False).reset_index(drop=True)
    df["last_updated"] = datetime.today().strftime("%Y-%m-%d")

    output_path = Path(scores_dir) / "financial_scores.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Financial scores saved to {output_path}")
    logger.info("Financial scores saved to %s", output_path)

    return df
