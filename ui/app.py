"""Flask web UI for Behavioural Business Signals.

Routes:
    GET /                  — Main dashboard scoreboard
    GET /api/scores        — Combined scores for all companies as JSON
    GET /api/company/<ticker> — Full data for a single company as JSON
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template

import config

logger = logging.getLogger(__name__)


def _load_scores() -> pd.DataFrame:
    """Load and merge financial and behavioural score CSVs.

    Returns:
        Merged DataFrame with both scores. Returns empty DataFrame if no files exist.
    """
    fin_path = Path(config.SCORES_DIR) / "financial_scores.csv"
    beh_path = Path(config.SCORES_DIR) / "behavioural_scores.csv"

    fin_df = pd.read_csv(fin_path) if fin_path.exists() else pd.DataFrame()
    beh_df = pd.read_csv(beh_path) if beh_path.exists() else pd.DataFrame()

    companies_path = Path(config.DATA_DIR) / "companies.json"
    with companies_path.open() as f:
        companies_data = json.load(f)

    base_df = pd.DataFrame([
        {
            "ticker": c["ticker"],
            "company_name": c["name"],
            "sector": c["sector"],
        }
        for c in companies_data["companies"]
    ])

    if not fin_df.empty and "financial_score" in fin_df.columns:
        base_df = base_df.merge(
            fin_df[["ticker", "financial_score"]], on="ticker", how="left"
        )
    else:
        base_df["financial_score"] = None

    if not beh_df.empty and "behavioural_score" in beh_df.columns:
        base_df = base_df.merge(
            beh_df[["ticker", "behavioural_score"]], on="ticker", how="left"
        )
    else:
        base_df["behavioural_score"] = None

    return base_df


def _quadrant_label(fin_score, beh_score) -> str:
    """Determine the quadrant label based on both scores relative to 50.

    Args:
        fin_score: Financial score (0–100) or None.
        beh_score: Behavioural score (0–100) or None.

    Returns:
        One of: "Strong / Strong", "Strong / Weak", "Weak / Strong",
        "Weak / Weak", or "Pending Data".
    """
    if fin_score is None or beh_score is None or pd.isna(fin_score) or pd.isna(beh_score):
        return "Pending Data"
    fin_strong = float(fin_score) >= 50
    beh_strong = float(beh_score) >= 50
    if fin_strong and beh_strong:
        return "Strong / Strong"
    if fin_strong and not beh_strong:
        return "Strong / Weak"
    if not fin_strong and beh_strong:
        return "Weak / Strong"
    return "Weak / Weak"


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def index():
        """Render the main dashboard."""
        df = _load_scores()
        rows = []
        for _, row in df.iterrows():
            fin = row.get("financial_score")
            beh = row.get("behavioural_score")
            rows.append({
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "sector": row["sector"],
                "financial_score": f"{float(fin):.1f}" if pd.notna(fin) and fin is not None else "—",
                "behavioural_score": f"{float(beh):.1f}" if pd.notna(beh) and beh is not None else "—",
                "quadrant": _quadrant_label(fin, beh),
            })

        return render_template(
            "index.html",
            rows=rows,
            last_updated=date.today().isoformat(),
        )

    @app.route("/api/scores")
    def api_scores():
        """Return combined scores for all companies as JSON."""
        df = _load_scores()
        records = []
        for _, row in df.iterrows():
            fin = row.get("financial_score")
            beh = row.get("behavioural_score")
            records.append({
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "sector": row["sector"],
                "financial_score": float(fin) if pd.notna(fin) and fin is not None else None,
                "behavioural_score": float(beh) if pd.notna(beh) and beh is not None else None,
                "quadrant": _quadrant_label(fin, beh),
            })
        return jsonify(records)

    @app.route("/api/company/<ticker>")
    def api_company(ticker: str):
        """Return full available data for a single company as JSON.

        Args:
            ticker: Stock ticker symbol (case-insensitive).
        """
        ticker = ticker.upper()

        companies_path = Path(config.DATA_DIR) / "companies.json"
        with companies_path.open() as f:
            companies_data = json.load(f)

        company = next(
            (c for c in companies_data["companies"] if c["ticker"] == ticker),
            None,
        )
        if company is None:
            return jsonify({"error": f"Ticker '{ticker}' not found"}), 404

        result = dict(company)

        fin_path = Path(config.SCORES_DIR) / "financial_scores.csv"
        if fin_path.exists():
            fin_df = pd.read_csv(fin_path)
            match = fin_df[fin_df["ticker"] == ticker]
            if not match.empty:
                result["financial_data"] = match.iloc[0].dropna().to_dict()

        beh_path = Path(config.SCORES_DIR) / "behavioural_scores.csv"
        if beh_path.exists():
            beh_df = pd.read_csv(beh_path)
            match = beh_df[beh_df["ticker"] == ticker]
            if not match.empty:
                result["behavioural_data"] = match.iloc[0].dropna().to_dict()

        return jsonify(result)

    return app
