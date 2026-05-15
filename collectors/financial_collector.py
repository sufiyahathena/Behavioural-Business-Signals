"""
financial_collector.py

Fetches financial metrics for all 19 companies using a waterfall:
    1. Financial Modeling Prep (FMP) — primary source, clean structured data
    2. yfinance — fallback for any gaps

Metrics collected:
    1.  revenue_growth       — YoY revenue growth (%)
    2.  gross_margin         — Gross profit / Revenue (%)
    3.  operating_margin     — Operating income / Revenue (%)
    4.  net_profit_margin    — Net income / Revenue (%)
    5.  fcf_margin           — Free cash flow / Revenue (%)
    6.  debt_to_equity       — Total debt / Stockholders equity
    7.  current_ratio        — Current assets / Current liabilities
    8.  roe                  — Net income / Stockholders equity (%)
    9.  roa                  — Net income / Total assets (%)
    10. interest_coverage    — EBIT / Interest expense
"""

import requests
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
import sys
import os

# Add project root to path for config import
sys.path.append(str(Path(__file__).parent.parent))
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

TICKERS = [
    "EL", "ULTA", "ELF", "COTY", "OLPX", "SBH", "ODD", "LRLCY",
    "ANF", "AEO", "URBN", "GAP", "LEVI", "RVLV", "LULU", "ONON",
    "RL", "COLM", "BIRK"
]

COMPANY_NAMES = {
    "EL": "Estée Lauder", "ULTA": "Ulta Beauty", "ELF": "e.l.f. Beauty",
    "COTY": "Coty Inc.", "OLPX": "Olaplex", "SBH": "Sally Beauty",
    "ODD": "Oddity Tech", "LRLCY": "L'Oréal", "ANF": "Abercrombie & Fitch",
    "AEO": "American Eagle", "URBN": "Urban Outfitters", "GAP": "Gap Inc.",
    "LEVI": "Levi Strauss", "RVLV": "Revolve", "LULU": "Lululemon",
    "ONON": "On Holding", "RL": "Ralph Lauren", "COLM": "Columbia Sportswear",
    "BIRK": "Birkenstock"
}

# ─────────────────────────────────────────────
# FMP HELPERS
# ─────────────────────────────────────────────

def fmp_get(endpoint: str) -> list:
    """Call FMP v3 API and return JSON list, or empty list on failure.

    Note: FMP deprecated v3 endpoints for new accounts after August 2025.
    This function is kept in place for future compatibility but will return []
    gracefully, allowing the yfinance waterfall fallback to handle all metrics.
    """
    if not config.FMP_API_KEY:
        return []
    url = f"https://financialmodelingprep.com/api/v3/{endpoint}&apikey={config.FMP_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if isinstance(data, dict) and "Error Message" in data:
            logger.warning(f"FMP error: {data['Error Message']}")
            return []
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"FMP request failed: {e}")
    return []


def fetch_fmp_metrics(ticker: str) -> dict:
    """
    Fetch all 10 metrics from FMP for a single ticker.
    Returns dict with metric values (NaN if unavailable).
    """
    result = {}

    # Income statement — most recent annual
    income = fmp_get(f"income-statement/{ticker}?limit=2&period=annual")
    balance = fmp_get(f"balance-sheet-statement/{ticker}?limit=1&period=annual")
    cashflow = fmp_get(f"cash-flow-statement/{ticker}?limit=1&period=annual")
    ratios = fmp_get(f"ratios/{ticker}?limit=1&period=annual")

    if not income or len(income) < 1:
        return result  # FMP has nothing for this ticker

    curr = income[0]
    prev = income[1] if len(income) > 1 else {}
    bal  = balance[0] if balance else {}
    cf   = cashflow[0] if cashflow else {}
    rat  = ratios[0] if ratios else {}

    def safe(d: dict, key: str):
        val = d.get(key)
        return float(val) if val is not None and val != 0 else np.nan

    # Revenue growth
    rev_curr = safe(curr, "revenue")
    rev_prev = safe(prev, "revenue") if prev else np.nan
    if pd.notna(rev_curr) and pd.notna(rev_prev) and rev_prev != 0:
        result["revenue_growth"] = ((rev_curr - rev_prev) / abs(rev_prev)) * 100

    # Gross margin
    gp = safe(curr, "grossProfit")
    result["gross_margin"] = (gp / rev_curr * 100) if pd.notna(gp) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

    # Operating margin
    op = safe(curr, "operatingIncome")
    result["operating_margin"] = (op / rev_curr * 100) if pd.notna(op) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

    # Net profit margin
    ni = safe(curr, "netIncome")
    result["net_profit_margin"] = (ni / rev_curr * 100) if pd.notna(ni) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

    # FCF margin
    fcf = safe(cf, "freeCashFlow")
    result["fcf_margin"] = (fcf / rev_curr * 100) if pd.notna(fcf) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

    # Debt to equity
    result["debt_to_equity"] = safe(rat, "debtEquityRatio")

    # Current ratio
    result["current_ratio"] = safe(rat, "currentRatio")

    # ROE
    result["roe"] = safe(rat, "returnOnEquity") * 100 if pd.notna(safe(rat, "returnOnEquity")) else np.nan

    # ROA
    result["roa"] = safe(rat, "returnOnAssets") * 100 if pd.notna(safe(rat, "returnOnAssets")) else np.nan

    # Interest coverage
    result["interest_coverage"] = safe(rat, "interestCoverage")

    # Absolute reported figures
    result["abs_revenue"] = safe(curr, "revenue")
    result["abs_gross_profit"] = safe(curr, "grossProfit")
    result["abs_operating_income"] = safe(curr, "operatingIncome")
    result["abs_net_income"] = safe(curr, "netIncome")
    result["abs_fcf"] = safe(cf, "freeCashFlow")
    result["abs_total_debt"] = safe(bal, "totalDebt")
    result["abs_total_assets"] = safe(bal, "totalAssets")
    result["abs_ebit"] = safe(curr, "operatingIncome")
    result["abs_current_assets"] = safe(bal, "totalCurrentAssets") if bal else np.nan
    result["abs_current_liabilities"] = safe(bal, "totalCurrentLiabilities") if bal else np.nan
    result["abs_equity"] = safe(bal, "totalStockholdersEquity") if bal else np.nan
    result["abs_revenue_prev"] = safe(prev, "revenue") if prev else np.nan

    return result


# ─────────────────────────────────────────────
# YFINANCE HELPERS
# ─────────────────────────────────────────────

def safe_get_yf(df: pd.DataFrame, row_name: str, col_index: int = 0):
    """Safely extract a value from a yfinance DataFrame by row name."""
    try:
        matches = [r for r in df.index if row_name.lower() in r.lower()]
        if not matches:
            return np.nan
        val = df.loc[matches[0]].iloc[col_index]
        return float(val) if pd.notna(val) else np.nan
    except Exception:
        return np.nan


def fetch_yfinance_metrics(ticker: str) -> dict:
    """Fetch all 10 metrics from yfinance for a single ticker."""
    result = {}
    try:
        t = yf.Ticker(ticker)
        fin = t.financials
        bal = t.balance_sheet
        cf  = t.cashflow

        rev_curr = safe_get_yf(fin, "Total Revenue", 0)
        rev_prev = safe_get_yf(fin, "Total Revenue", 1)

        if pd.notna(rev_curr) and pd.notna(rev_prev) and rev_prev != 0:
            result["revenue_growth"] = ((rev_curr - rev_prev) / abs(rev_prev)) * 100

        gross_profit = safe_get_yf(fin, "Gross Profit", 0)
        if pd.isna(gross_profit):
            cost_rev = safe_get_yf(fin, "Cost Of Revenue", 0)
            if pd.notna(rev_curr) and pd.notna(cost_rev):
                gross_profit = rev_curr - cost_rev
        result["gross_margin"] = (gross_profit / rev_curr * 100) if pd.notna(gross_profit) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

        op_income = safe_get_yf(fin, "Operating Income", 0)
        if pd.isna(op_income):
            op_income = safe_get_yf(fin, "EBIT", 0)
        result["operating_margin"] = (op_income / rev_curr * 100) if pd.notna(op_income) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

        net_income = safe_get_yf(fin, "Net Income", 0)
        result["net_profit_margin"] = (net_income / rev_curr * 100) if pd.notna(net_income) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

        fcf = safe_get_yf(cf, "Free Cash Flow", 0)
        result["fcf_margin"] = (fcf / rev_curr * 100) if pd.notna(fcf) and pd.notna(rev_curr) and rev_curr != 0 else np.nan

        total_debt = safe_get_yf(bal, "Total Debt", 0)
        equity = safe_get_yf(bal, "Stockholders Equity", 0)
        if pd.isna(equity):
            equity = safe_get_yf(bal, "Common Stock Equity", 0)
        result["debt_to_equity"] = (total_debt / equity) if pd.notna(total_debt) and pd.notna(equity) and equity != 0 else np.nan

        curr_assets = safe_get_yf(bal, "Current Assets", 0)
        curr_liab   = safe_get_yf(bal, "Current Liabilities", 0)
        result["current_ratio"] = (curr_assets / curr_liab) if pd.notna(curr_assets) and pd.notna(curr_liab) and curr_liab != 0 else np.nan

        result["roe"] = (net_income / equity * 100) if pd.notna(net_income) and pd.notna(equity) and equity != 0 else np.nan

        total_assets = safe_get_yf(bal, "Total Assets", 0)
        result["roa"] = (net_income / total_assets * 100) if pd.notna(net_income) and pd.notna(total_assets) and total_assets != 0 else np.nan

        ebit = safe_get_yf(fin, "EBIT", 0)
        if pd.isna(ebit):
            ebit = op_income
        interest_exp = safe_get_yf(fin, "Interest Expense", 0)
        if pd.isna(interest_exp):
            interest_exp = safe_get_yf(fin, "Net Interest Income", 0)
            if pd.notna(interest_exp):
                interest_exp = abs(interest_exp)
        result["interest_coverage"] = (ebit / interest_exp) if pd.notna(ebit) and pd.notna(interest_exp) and interest_exp != 0 else np.nan

        # Absolute reported figures
        result["abs_revenue"] = rev_curr
        result["abs_gross_profit"] = gross_profit
        result["abs_operating_income"] = op_income
        result["abs_net_income"] = net_income
        result["abs_fcf"] = fcf
        result["abs_total_debt"] = total_debt
        result["abs_total_assets"] = total_assets
        result["abs_ebit"] = ebit
        result["abs_current_assets"] = safe_get_yf(bal, "Current Assets", 0)
        result["abs_current_liabilities"] = safe_get_yf(bal, "Current Liabilities", 0)
        result["abs_equity"] = equity
        result["abs_revenue_prev"] = rev_prev

    except Exception as e:
        logger.warning(f"yfinance failed for {ticker}: {e}")

    return result


# ─────────────────────────────────────────────
# WATERFALL MERGER
# ─────────────────────────────────────────────

METRICS = [
    "revenue_growth", "gross_margin", "operating_margin", "net_profit_margin",
    "fcf_margin", "debt_to_equity", "current_ratio", "roe", "roa", "interest_coverage"
]

ABS_FIELDS = [
    "abs_revenue", "abs_gross_profit", "abs_operating_income", "abs_net_income",
    "abs_fcf", "abs_total_debt", "abs_total_assets", "abs_ebit",
    "abs_current_assets", "abs_current_liabilities", "abs_equity", "abs_revenue_prev",
]


def merge_waterfall(fmp: dict, yf_data: dict) -> tuple[dict, dict]:
    """
    Merge FMP and yfinance data using waterfall logic.
    FMP is preferred. yfinance fills any NaN gaps.

    Returns:
        merged dict of metric values
        source dict showing which source was used per metric
    """
    merged = {}
    sources = {}

    for metric in METRICS:
        fmp_val = fmp.get(metric, np.nan)
        yf_val  = yf_data.get(metric, np.nan)

        if pd.notna(fmp_val):
            merged[metric] = fmp_val
            sources[metric] = "FMP"
        elif pd.notna(yf_val):
            merged[metric] = yf_val
            sources[metric] = "yfinance"
        else:
            merged[metric] = np.nan
            sources[metric] = "missing"

    # Absolute figures: prefer FMP, fall back to yfinance
    for field in ABS_FIELDS:
        fmp_val = fmp.get(field, np.nan)
        yf_val  = yf_data.get(field, np.nan)
        merged[field] = fmp_val if pd.notna(fmp_val) else yf_val

    return merged, sources


def fetch_metrics(ticker: str) -> dict:
    """
    Fetch all 10 financial metrics for a single ticker using waterfall.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict of metric name -> value, plus source tracking
    """
    logger.info(f"Fetching {ticker}...")

    fmp_data = fetch_fmp_metrics(ticker)
    yf_data  = fetch_yfinance_metrics(ticker)
    merged, sources = merge_waterfall(fmp_data, yf_data)

    # Log source summary
    fmp_count  = sum(1 for s in sources.values() if s == "FMP")
    yf_count   = sum(1 for s in sources.values() if s == "yfinance")
    miss_count = sum(1 for s in sources.values() if s == "missing")
    logger.info(f"  {ticker}: FMP={fmp_count} metrics, yfinance={yf_count}, missing={miss_count}")

    result = {
        "ticker": ticker,
        "company_name": COMPANY_NAMES.get(ticker, ticker),
        **merged,
        "data_sources": str(sources)
    }

    return result


def fetch_all_companies() -> pd.DataFrame:
    """Fetch metrics for all 19 companies using waterfall."""
    results = []
    for ticker in TICKERS:
        metrics = fetch_metrics(ticker)
        results.append(metrics)

    df = pd.DataFrame(results)
    df["last_updated"] = datetime.today().strftime("%Y-%m-%d")
    return df


def save_financial_data(df: pd.DataFrame, output_path: str = "data/financial/financial_raw.csv") -> None:
    """Save financial data to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"Saved financial data to {path} ({len(df)} companies)")


if __name__ == "__main__":
    df = fetch_all_companies()
    save_financial_data(df)
    print("\n── Financial Data Summary ──")
    cols = ["ticker", "company_name", "revenue_growth", "gross_margin", "operating_margin", "net_profit_margin"]
    print(df[cols].to_string(index=False))
