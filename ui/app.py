"""Flask web UI for Behavioural Business Signals.

Routes:
    GET /                       — Main dashboard scoreboard
    GET /company/<ticker>       — Company detail page
    GET /api/scores             — Combined scores for all companies as JSON
    GET /api/company/<ticker>   — Full data for a single company as JSON
"""

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, redirect, render_template, url_for

import config
from collectors.news_collector import fetch_company_news

logger = logging.getLogger(__name__)

_FINANCIAL_METRIC_LABELS = {
    "revenue_growth": "Revenue Growth",
    "gross_margin": "Gross Margin",
    "operating_margin": "Operating Margin",
    "net_profit_margin": "Net Profit Margin",
    "fcf_margin": "FCF Margin",
    "debt_to_equity": "Debt to Equity",
    "current_ratio": "Current Ratio",
    "roe": "Return on Equity (ROE)",
    "roa": "Return on Assets (ROA)",
    "interest_coverage": "Interest Coverage Ratio",
}

_BEHAVIOURAL_METRIC_LABELS = {
    "google_trends_score": "Google Trends Score",
    "trustpilot_rating": "Trustpilot Rating",
    "trustpilot_review_count": "Trustpilot Review Count",
    "app_rating": "App Rating",
    "reddit_sentiment": "Reddit Sentiment Score",
    "glassdoor_overall": "Glassdoor Overall Rating",
    "glassdoor_ceo_approval": "Glassdoor CEO Approval",
    "glassdoor_recommend": "Glassdoor Recommend %",
}

_EMPTY_GLASSDOOR = {
    "overall_rating": "—",
    "ceo_approval_pct": "—",
    "recommend_to_friend_pct": "—",
    "culture_rating": "—",
    "work_life_balance_rating": "—",
    "last_updated": "—",
}


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


def _score_bar_colour(score) -> str:
    """Return a CSS class name for the score bar based on score value.

    Args:
        score: Numeric score (0–100) or None.

    Returns:
        "green" if > 66, "amber" if 33–66, "red" if < 33, "pending" if None.
    """
    if score is None:
        return "pending"
    if score > 66:
        return "green"
    if score >= 33:
        return "amber"
    return "red"


def _gd_display_val(row: pd.Series, col: str, fmt: str = "float") -> str:
    """Format a Glassdoor CSV value for display.

    Returns "—" for NaN, None, or zero placeholder values.

    Args:
        row: Pandas Series for a single Glassdoor CSV row.
        col: Column name to extract.
        fmt: "float" for one decimal place, "pct" for integer percentage with % sign.

    Returns:
        Formatted string or "—".
    """
    v = row.get(col)
    if not pd.notna(v):
        return "—"
    try:
        fv = float(v)
    except (ValueError, TypeError):
        return "—"
    if fv == 0.0:
        return "—"
    if fmt == "pct":
        return f"{fv:.0f}%"
    return f"{fv:.1f}"


def _fmt_metric(val) -> str:
    """Format a raw numeric metric value for display in the metrics table.

    Args:
        val: Raw value from the scores CSV (float, int, or pandas NA).

    Returns:
        Four-decimal-place string, or "—" for missing values.
    """
    try:
        return f"{float(val):.4f}" if pd.notna(val) else "—"
    except (ValueError, TypeError):
        return "—"


def _fmt_norm(val) -> str:
    """Format a normalised metric value for display in the metrics table.

    Args:
        val: Normalised value (0–1) or pandas NA.

    Returns:
        Three-decimal-place string, or "—" for missing values.
    """
    try:
        return f"{float(val):.3f}" if pd.notna(val) else "—"
    except (ValueError, TypeError):
        return "—"


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.route("/")
    def root():
        """Redirect root to the home/cover page."""
        return redirect(url_for("home"))

    @app.route("/companies")
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
            active_page="companies",
        )

    @app.route("/company/<ticker>")
    def company_detail(ticker: str):
        """Render the company detail page.

        Args:
            ticker: Stock ticker symbol from the URL (case-insensitive).
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
            return render_template(
                "company.html",
                not_found=True,
                ticker=ticker,
                company=None,
                fin_score=None,
                fin_score_colour="pending",
                fin_score_pct=0,
                fin_metrics=[],
                beh_score=None,
                beh_score_colour="pending",
                beh_score_pct=0,
                beh_metrics=[],
                glassdoor=dict(_EMPTY_GLASSDOOR),
                news_articles=[],
                active_page="companies",
            ), 404

        # ── Financial data ────────────────────────────────────────
        fin_score = None
        fin_metrics = []
        fin_path = Path(config.SCORES_DIR) / "financial_scores.csv"
        if fin_path.exists():
            fin_df = pd.read_csv(fin_path)
            fin_match = fin_df[fin_df["ticker"] == ticker]
            if not fin_match.empty:
                fin_row = fin_match.iloc[0]
                raw_fin = fin_row.get("financial_score")
                fin_score = float(raw_fin) if pd.notna(raw_fin) else None
                for key, label in _FINANCIAL_METRIC_LABELS.items():
                    fin_metrics.append({
                        "label": label,
                        "raw": _fmt_metric(fin_row.get(key)),
                        "norm": _fmt_norm(fin_row.get(f"{key}_norm")),
                    })

        # ── Behavioural data ──────────────────────────────────────
        beh_score = None
        beh_metrics = []
        beh_path = Path(config.SCORES_DIR) / "behavioural_scores.csv"
        if beh_path.exists():
            beh_df = pd.read_csv(beh_path)
            beh_match = beh_df[beh_df["ticker"] == ticker]
            if not beh_match.empty:
                beh_row = beh_match.iloc[0]
                raw_beh = beh_row.get("behavioural_score")
                beh_score = float(raw_beh) if pd.notna(raw_beh) else None
                for key, label in _BEHAVIOURAL_METRIC_LABELS.items():
                    beh_metrics.append({
                        "label": label,
                        "raw": _fmt_metric(beh_row.get(key)),
                        "norm": _fmt_norm(beh_row.get(f"{key}_norm")),
                    })

        # ── Glassdoor data ────────────────────────────────────────
        glassdoor = dict(_EMPTY_GLASSDOOR)
        gd_path = Path(config.BEHAVIOURAL_DIR) / "glassdoor_manual.csv"
        if gd_path.exists():
            gd_df = pd.read_csv(gd_path)
            gd_match = gd_df[gd_df["ticker"] == ticker]
            if not gd_match.empty:
                gd_row = gd_match.iloc[0]
                lu = gd_row.get("last_updated")
                glassdoor = {
                    "overall_rating": _gd_display_val(gd_row, "overall_rating"),
                    "ceo_approval_pct": _gd_display_val(gd_row, "ceo_approval_pct", "pct"),
                    "recommend_to_friend_pct": _gd_display_val(gd_row, "recommend_to_friend_pct", "pct"),
                    "culture_rating": _gd_display_val(gd_row, "culture_rating"),
                    "work_life_balance_rating": _gd_display_val(gd_row, "work_life_balance_rating"),
                    "last_updated": str(lu) if pd.notna(lu) else "—",
                }

        # Fetch live news — returns [] gracefully if unreachable
        news_articles = fetch_company_news(
            company_name=company["name"],
            ticker=company["ticker"],
            max_articles=8,
        )

        return render_template(
            "company.html",
            not_found=False,
            ticker=ticker,
            company=company,
            fin_score=f"{fin_score:.1f}" if fin_score is not None else None,
            fin_score_colour=_score_bar_colour(fin_score),
            fin_score_pct=int(fin_score) if fin_score is not None else 0,
            fin_metrics=fin_metrics,
            beh_score=f"{beh_score:.1f}" if beh_score is not None else None,
            beh_score_colour=_score_bar_colour(beh_score),
            beh_score_pct=int(beh_score) if beh_score is not None else 0,
            beh_metrics=beh_metrics,
            glassdoor=glassdoor,
            news_articles=news_articles,
            active_page="companies",
        )

    @app.route("/home")
    def home():
        """Render the cover / home page."""
        return render_template("home.html", active_page="home")

    @app.route("/financial-breakdown")
    def financial_breakdown():
        """Render the financial breakdown placeholder page."""
        return render_template("financial_breakdown.html", active_page="financial")

    @app.route("/behavioural-breakdown")
    def behavioural_breakdown():
        """Render the behavioural breakdown placeholder page."""
        return render_template("behavioural_breakdown.html", active_page="behavioural")

    @app.route("/about")
    def about():
        """Render the about page."""
        return render_template("about.html", active_page="about")

    @app.route("/ethics")
    def ethics():
        return render_template("ethics.html", active_page="ethics")

    @app.route("/purpose")
    def purpose():
        """Render the purpose placeholder page."""
        return render_template("purpose.html", active_page="purpose")

    @app.route("/visualise")
    def visualise():
        return render_template("visualise.html", active_page="visualise")

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
