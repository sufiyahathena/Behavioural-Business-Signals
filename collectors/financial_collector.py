"""Financial data collector.

Fetches income statement, balance sheet, and cash flow metrics for each company
using yfinance (free, no API key) and Financial Modeling Prep (FMP) as a paid
fallback for more reliable structured data.

Outputs a DataFrame with one row per company containing the 10 financial metrics
required by the financial scorer.
"""

import logging
from pathlib import Path

import pandas as pd
import yfinance as yf
import requests

logger = logging.getLogger(__name__)


def fetch_financials_yfinance(ticker: str) -> dict:
    """Fetch key financial metrics for a single ticker using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g. "EL", "LULU").

    Returns:
        Dictionary containing the 10 financial metrics. Returns empty dict on failure.
    """
    # TODO: instantiate yf.Ticker(ticker), pull .financials, .balance_sheet,
    # .cashflow; compute revenue_growth, gross_margin, operating_margin,
    # net_profit_margin, fcf_margin, debt_to_equity, current_ratio, roe, roa,
    # interest_coverage from the raw statements; return as flat dict.
    pass


def fetch_financials_fmp(ticker: str, api_key: str) -> dict:
    """Fetch key financial metrics for a single ticker using Financial Modeling Prep API.

    Args:
        ticker: Stock ticker symbol.
        api_key: FMP API key from config.FMP_API_KEY.

    Returns:
        Dictionary containing the 10 financial metrics. Returns empty dict on failure.
    """
    # TODO: call FMP endpoints /income-statement, /balance-sheet-statement,
    # /cash-flow-statement with ?apikey=api_key&limit=1; parse JSON responses;
    # compute the same 10 metrics as fetch_financials_yfinance; return flat dict.
    pass


def fetch_all_companies(tickers: list) -> pd.DataFrame:
    """Fetch financial metrics for all companies in the ticker list.

    Tries yfinance first; falls back to FMP if yfinance returns incomplete data.

    Args:
        tickers: List of ticker symbols to fetch.

    Returns:
        DataFrame with one row per ticker and columns for each financial metric.
    """
    # TODO: iterate over tickers; call fetch_financials_yfinance; if result is
    # empty or missing >3 metrics, call fetch_financials_fmp as fallback;
    # collect results into a list of dicts; return pd.DataFrame(results).
    pass


def save_financial_data(df: pd.DataFrame, output_path: str) -> None:
    """Save the financial metrics DataFrame to CSV.

    Args:
        df: DataFrame returned by fetch_all_companies.
        output_path: Destination file path (e.g. "data/financial/raw_financials.csv").
    """
    # TODO: add a last_updated column with today's date; ensure output directory
    # exists using pathlib; call df.to_csv(output_path, index=False); log confirmation.
    pass
