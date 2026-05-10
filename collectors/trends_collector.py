"""Google Trends collector.

Uses pytrends (unofficial Google Trends API wrapper) to measure relative search
interest for each company's primary brand name over the last 12 months in the US.
Higher average interest = stronger consumer search attention signal.
"""

import logging
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)


def fetch_trends(keyword: str, timeframe: str, geo: str) -> pd.DataFrame:
    """Fetch Google Trends interest-over-time data for a single keyword.

    Args:
        keyword: Brand name or search term to query (e.g. "Lululemon").
        timeframe: Time range string accepted by pytrends (e.g. "today 12-m").
        geo: Geographic filter (e.g. "US").

    Returns:
        DataFrame with a DatetimeIndex and a single column for the keyword's
        weekly interest values (0–100 scale as returned by Google Trends).
    """
    # TODO: instantiate TrendReq(hl="en-US", tz=360); call build_payload with
    # [keyword], timeframe=timeframe, geo=geo; return interest_over_time()
    # result dropping the isPartial column.
    pass


def fetch_trends_for_all(companies: list) -> pd.DataFrame:
    """Fetch Google Trends data for every company in the list.

    Queries are batched in groups of 5 (pytrends limit) using a reference term
    to enable cross-company comparison on the same relative scale.

    Args:
        companies: List of dicts, each with at least "ticker" and "name" keys.

    Returns:
        DataFrame with columns: ticker, company_name, google_trends_score.
    """
    # TODO: loop through companies; call fetch_trends for each brand name;
    # apply compute_average_interest; build results list; add a small sleep
    # between requests to avoid rate limiting; return pd.DataFrame(results).
    pass


def compute_average_interest(trends_df: pd.DataFrame) -> float:
    """Compute the mean weekly interest score from a trends time series.

    Args:
        trends_df: DataFrame returned by fetch_trends (weekly interest values).

    Returns:
        Mean interest value as a float (0–100).
    """
    # TODO: return float(trends_df.iloc[:, 0].mean()) handling empty DataFrame
    # by returning 0.0.
    pass
