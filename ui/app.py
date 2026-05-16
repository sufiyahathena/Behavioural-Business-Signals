"""Flask web UI for Behavioural Business Signals.

Routes:
    GET /                       — Main dashboard scoreboard
    GET /company/<ticker>       — Company detail page
    GET /api/scores             — Combined scores for all companies as JSON
    GET /api/company/<ticker>   — Full data for a single company as JSON
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests as http_requests
from flask import Flask, jsonify, redirect, render_template, request, url_for

import config


def _get_market_caps() -> dict:
    """Fetch current market caps from yfinance for all companies.

    Caches results in data/financial/market_caps.csv and refreshes
    if the cache is older than 24 hours.

    Returns:
        Dict of ticker -> market_cap_billions (float)
    """
    import yfinance as yf

    cache_path = Path(config.DATA_DIR) / "financial" / "market_caps.csv"

    # Check if cache exists and is fresh (less than 24 hours old)
    if cache_path.exists():
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if cache_age < timedelta(hours=24):
            df = pd.read_csv(cache_path)
            return dict(zip(df["ticker"], df["market_cap_b"]))

    # Fetch from yfinance
    tickers = [
        "EL", "ULTA", "ELF", "COTY", "OLPX", "SBH", "ODD", "LRLCY",
        "ANF", "AEO", "URBN", "GAP", "LEVI", "RVLV", "LULU", "ONON",
        "RL", "COLM", "BIRK"
    ]

    market_caps = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            mc = info.get("marketCap") or info.get("market_cap")
            market_caps[ticker] = round(mc / 1e9, 1) if mc else None
        except Exception:
            market_caps[ticker] = None

    # Save cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"ticker": t, "market_cap_b": v} for t, v in market_caps.items()
    ]).to_csv(cache_path, index=False)

    return market_caps
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
    "google_trends_score_us": "Google Trends Score (US)",
    "google_trends_score_global": "Google Trends Score (Global)",
    "trustpilot_rating": "Trustpilot Rating",
    "app_rating": "App Rating",
    "youtube_subscribers": "YouTube Subscribers",
    "glassdoor_overall": "Glassdoor Overall Rating",
    "glassdoor_ceo_approval": "Glassdoor CEO Approval %",
    "glassdoor_recommend": "Glassdoor Recommend %",
}

_EMPTY_GLASSDOOR = {
    "overall_rating": "—",
    "ceo_approval_pct": "—",
    "recommend_to_friend_pct": "—",
    "culture_rating": "—",
    "work_life_balance_rating": "—",
    "diversity_rating": "—",
    "senior_management_rating": "—",
    "compensation_rating": "—",
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
        One of: "Dual Strength", "Financial Leader", "Hidden Momentum",
        "Under Pressure", or "Pending Data".
    """
    if fin_score is None or beh_score is None or pd.isna(fin_score) or pd.isna(beh_score):
        return "Pending Data"
    fin_strong = float(fin_score) >= 50
    beh_strong = float(beh_score) >= 50
    if fin_strong and beh_strong:
        return "Dual Strength"
    if fin_strong and not beh_strong:
        return "Financial Leader"
    if not fin_strong and beh_strong:
        return "Hidden Momentum"
    return "Under Pressure"


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


def _fmt_beh_metric(key: str, val) -> str:
    """Format a raw behavioural metric value for display.

    Uses context-aware formatting based on the metric type:
    - Review counts: integer with comma separator
    - Percentage fields (CEO approval, recommend): shown as X%
    - Ratings and scores: one decimal place

    Args:
        key: The metric key (e.g. "trustpilot_review_count").
        val: Raw value from the scores CSV.

    Returns:
        Formatted string, or "—" for missing values.
    """
    try:
        if not pd.notna(val):
            return "—"
        fv = float(val)
    except (ValueError, TypeError):
        return "—"

    # Integer fields — review counts and subscriber counts
    if key in ("trustpilot_review_count", "youtube_subscribers"):
        return f"{int(fv):,}"

    # Percentage fields — stored as 0–1 after conversion
    if key in ("glassdoor_ceo_approval", "glassdoor_recommend"):
        return f"{fv * 100:.0f}%"

    # Score fields — Google Trends (0–100 scale)
    if key in ("google_trends_score_us", "google_trends_score_global"):
        return f"{fv:.1f}"

    # Default: one decimal place for ratings
    return f"{fv:.1f}"


def _format_dollars(val) -> str:
    """Format an absolute dollar value as $XB or $XM for display."""
    try:
        fv = float(val)
    except (ValueError, TypeError):
        return "—"
    if not pd.notna(fv):
        return "—"
    abs_fv = abs(fv)
    sign = "-" if fv < 0 else ""
    if abs_fv >= 1e9:
        return f"{sign}${abs_fv / 1e9:.2f}B"
    if abs_fv >= 1e6:
        return f"{sign}${abs_fv / 1e6:.1f}M"
    return f"{sign}${abs_fv:,.0f}"


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask app instance.
    """
    import os as _os
    _here = _os.path.dirname(_os.path.abspath(__file__))
    app = Flask(__name__,
                template_folder=_os.path.join(_here, "templates"),
                static_folder=_os.path.join(_here, "static"))

    @app.template_filter("format_dollars")
    def format_dollars_filter(val):
        return _format_dollars(val)

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
                financial_data={},
                financial_norm={},
                peer_context={},
                abs_figures={},
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
        financial_data = {}
        financial_norm = {}
        peer_context = {}
        abs_figures = {}
        fin_path = Path(config.SCORES_DIR) / "financial_scores.csv"
        if fin_path.exists():
            fin_df = pd.read_csv(fin_path)
            fin_match = fin_df[fin_df["ticker"] == ticker]
            if not fin_match.empty:
                fin_row = fin_match.iloc[0]
                raw_fin = fin_row.get("financial_score")
                fin_score = float(raw_fin) if pd.notna(raw_fin) else None
                for key, label in _FINANCIAL_METRIC_LABELS.items():
                    val = fin_row.get(key)
                    norm_val = fin_row.get(f"norm_{key}")
                    fin_metrics.append({
                        "label": label,
                        "key": key,
                        "raw": _fmt_metric(val),
                        "norm": _fmt_norm(norm_val),
                    })
                    if pd.notna(val):
                        financial_data[key] = round(float(val), 4)
                    if pd.notna(norm_val):
                        financial_norm[key] = round(float(norm_val), 3)

            # Absolute figures from financial_raw.csv
            _abs_fields = [
                "abs_revenue", "abs_gross_profit", "abs_operating_income",
                "abs_net_income", "abs_fcf", "abs_total_debt", "abs_total_assets", "abs_ebit",
                "abs_current_assets", "abs_current_liabilities", "abs_equity", "abs_revenue_prev",
            ]
            raw_path = Path(config.FINANCIAL_DIR) / "financial_raw.csv"
            if raw_path.exists():
                raw_df = pd.read_csv(raw_path)
                raw_match = raw_df[raw_df["ticker"] == ticker]
                if not raw_match.empty:
                    raw_row = raw_match.iloc[0]
                    for field in _abs_fields:
                        v = raw_row.get(field)
                        if pd.notna(v):
                            abs_figures[field] = float(v)

            # Peer context: min/max ticker and value for each metric
            _peer_metrics = list(_FINANCIAL_METRIC_LABELS.keys())
            for metric in _peer_metrics:
                if metric in fin_df.columns and fin_df[metric].notna().any():
                    peer_context[f"{metric}_min_ticker"] = fin_df.loc[fin_df[metric].idxmin(), "ticker"]
                    peer_context[f"{metric}_max_ticker"] = fin_df.loc[fin_df[metric].idxmax(), "ticker"]
                    peer_context[f"{metric}_min"] = float(fin_df[metric].min())
                    peer_context[f"{metric}_max"] = float(fin_df[metric].max())

        # ── Behavioural data ──────────────────────────────────────
        beh_score = None
        beh_metrics = []
        geo = config.COMPANY_GEOGRAPHY.get(ticker, "mixed")
        beh_path = Path(config.SCORES_DIR) / "behavioural_scores.csv"
        if beh_path.exists():
            beh_df = pd.read_csv(beh_path)
            beh_match = beh_df[beh_df["ticker"] == ticker]
            if not beh_match.empty:
                beh_row = beh_match.iloc[0]
                raw_beh = beh_row.get("behavioural_score")
                beh_score = float(raw_beh) if pd.notna(raw_beh) else None

                # Determine which Google Trends metric is zero-weighted for this company
                zero_weight_trends = set()
                if geo == "us":
                    zero_weight_trends.add("google_trends_score_global")
                elif geo == "global":
                    zero_weight_trends.add("google_trends_score_us")
                # mixed — both are used, nothing is zero-weighted

                for key, label in _BEHAVIOURAL_METRIC_LABELS.items():
                    raw_val = beh_row.get(key)
                    norm_val = beh_row.get(f"{key}_norm")
                    # Mark zero-weight Trends metrics as excluded (not used in scoring)
                    excluded = key in zero_weight_trends
                    beh_metrics.append({
                        "label": label,
                        "key": key,
                        "raw": _fmt_beh_metric(key, raw_val),
                        "norm": _fmt_norm(norm_val) if not excluded else "—",
                        "excluded": excluded,
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
                    "diversity_rating": _gd_display_val(gd_row, "diversity_rating"),
                    "senior_management_rating": _gd_display_val(gd_row, "senior_management_rating"),
                    "compensation_rating": _gd_display_val(gd_row, "compensation_rating"),
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
            financial_data=financial_data,
            financial_norm=financial_norm,
            peer_context=peer_context,
            abs_figures=abs_figures,
            beh_score=f"{beh_score:.1f}" if beh_score is not None else None,
            beh_score_colour=_score_bar_colour(beh_score),
            beh_score_pct=int(beh_score) if beh_score is not None else 0,
            beh_metrics=beh_metrics,
            beh_geography=geo,
            beh_last_updated="2026-05-14",
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

        # Hardcoded fallback market caps (in $B) in case yfinance is unavailable
        fallback_caps = {
            "EL": 16, "ULTA": 17, "ELF": 7, "COTY": 5, "OLPX": 1,
            "SBH": 1, "ODD": 3, "LRLCY": 220, "ANF": 4, "AEO": 2,
            "URBN": 4, "GAP": 3, "LEVI": 6, "RVLV": 1, "LULU": 38,
            "ONON": 18, "RL": 14, "COLM": 4, "BIRK": 9,
        }

        try:
            live_caps = _get_market_caps()
        except Exception:
            live_caps = {}

        records = []
        for _, row in df.iterrows():
            ticker = row["ticker"]
            fin = row.get("financial_score")
            beh = row.get("behavioural_score")
            mc = live_caps.get(ticker) or fallback_caps.get(ticker, 1)
            records.append({
                "ticker": ticker,
                "company_name": row["company_name"],
                "sector": row["sector"],
                "financial_score": float(fin) if pd.notna(fin) and fin is not None else None,
                "behavioural_score": float(beh) if pd.notna(beh) and beh is not None else None,
                "quadrant": _quadrant_label(fin, beh),
                "market_cap_b": mc,
            })
        return jsonify(records)

    @app.route("/api/chat", methods=["POST"])
    def chat_proxy():
        """Proxy chat requests to Gemini API keeping the key server-side."""
        try:
            data = request.get_json()
            messages = data.get("messages", [])
            system_prompt = data.get("system", "")

            # Convert messages to Gemini format
            gemini_contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

            response = http_requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={config.GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": gemini_contents,
                    "generationConfig": {
                        "maxOutputTokens": 1000,
                        "temperature": 0.7,
                    }
                },
                timeout=30,
            )

            result = response.json()
            logger.warning("Gemini raw response: %s", result)
            if "candidates" not in result:
                error = result.get("error", {})
                error_msg = error.get("message", "")
                status_code = error.get("code", 0)
                # Handle quota exceeded gracefully
                if status_code == 429 or "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                    return jsonify({"reply": "The assistant has reached its daily request limit and will be back tomorrow. In the meantime, you can explore the Financial Breakdown and Behavioural Breakdown pages for full methodology details."}), 200
                # Handle other errors
                return jsonify({"reply": "Sorry, the assistant is temporarily unavailable. Please try again in a moment."}), 200
            reply = result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"reply": reply}), 200

        except Exception as e:
            logger.error("Chat proxy error: %s", e)
            return jsonify({"error": str(e)}), 500

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

    @app.route("/api/stock/<ticker>")
    def api_stock(ticker: str):
        """Return current stock price for a ticker via yfinance."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            currency = info.get("currency", "USD")
            exchange = info.get("exchange", "")
            prev_close = info.get("previousClose")
            change_pct = None
            if price and prev_close:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)
            return jsonify({
                "ticker": ticker,
                "price": round(float(price), 2) if price else None,
                "currency": currency,
                "exchange": exchange,
                "change_pct": change_pct,
            })
        except Exception as e:
            logger.error("Stock price fetch error for %s: %s", ticker, e)
            return jsonify({"ticker": ticker, "price": None, "error": str(e)}), 200

    return app
