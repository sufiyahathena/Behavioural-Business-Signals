"""Google Trends collector.

Fetches relative search interest for each company's primary brand name over
the last 12 months, for both US and worldwide. Produces two scores per company:
google_trends_score_us and google_trends_score_global.
"""

import logging
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

import config

logger = logging.getLogger(__name__)

# Clean brand search terms — legal company names perform poorly on Trends
BRAND_SEARCH_TERMS = {
    "EL":    "Estee Lauder",
    "ULTA":  "Ulta Beauty",
    "ELF":   "elf Beauty",
    "COTY":  "Coty",
    "OLPX":  "Olaplex",
    "SBH":   "Sally Beauty",
    "ODD":   "Oddity Tech",
    "LRLCY": "L'Oreal",
    "ANF":   "Abercrombie Fitch",
    "AEO":   "American Eagle",
    "URBN":  "Urban Outfitters",
    "GAP":   "Gap",
    "LEVI":  "Levis",
    "RVLV":  "Revolve",
    "LULU":  "Lululemon",
    "ONON":  "On Running",
    "RL":    "Ralph Lauren",
    "COLM":  "Columbia Sportswear",
    "BIRK":  "Birkenstock",
}


def fetch_trends(keyword: str, timeframe: str = "today 12-m", geo: str = "US") -> pd.DataFrame:
    """Fetch Google Trends interest-over-time data for a single keyword.

    Args:
        keyword: Brand name or search term to query.
        timeframe: Time range string accepted by pytrends (e.g. "today 12-m").
        geo: Geographic filter — "US" for United States, "" for worldwide.

    Returns:
        DataFrame with weekly interest values (0-100). Empty DataFrame on failure.
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            logger.warning("No trends data returned for keyword: %s (geo=%s)", keyword, geo)
            return pd.DataFrame()
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        return df
    except Exception as e:
        logger.error("Failed to fetch trends for '%s' (geo=%s): %s", keyword, geo, e)
        return pd.DataFrame()


def compute_average_interest(trends_df: pd.DataFrame) -> float:
    """Compute the mean weekly interest score from a trends time series.

    Returns:
        Mean interest value as a float (0-100). Returns 0.0 for empty input.
    """
    if trends_df.empty:
        return 0.0
    return float(trends_df.iloc[:, 0].mean())


def fetch_trends_for_all(companies: list) -> pd.DataFrame:
    """Fetch US and global Google Trends data for every company in the list.

    Args:
        companies: List of dicts, each with at least "ticker" and "name" keys.

    Returns:
        DataFrame with columns: ticker, company_name,
        google_trends_score_us, google_trends_score_global.
    """
    results = []
    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        keyword = BRAND_SEARCH_TERMS.get(ticker, name)

        logger.info("Fetching Google Trends for %s (%s)", ticker, keyword)
        print(f"  Fetching trends: {ticker} — {keyword}")

        # US score
        us_df = fetch_trends(keyword, geo="US")
        us_score = compute_average_interest(us_df)
        time.sleep(10)

        # Global score
        global_df = fetch_trends(keyword, geo="")
        global_score = compute_average_interest(global_df)
        time.sleep(10)

        results.append({
            "ticker": ticker,
            "company_name": name,
            "google_trends_score_us": round(us_score, 2),
            "google_trends_score_global": round(global_score, 2),
        })

    return pd.DataFrame(results)


def run(
    companies: list = None,
    behavioural_dir: str = config.BEHAVIOURAL_DIR,
) -> pd.DataFrame:
    """Run the Google Trends collector and save results to CSV."""
    import json

    if companies is None:
        companies_path = Path(config.DATA_DIR) / "companies.json"
        with companies_path.open() as f:
            companies = json.load(f)["companies"]

    print(f"Collecting Google Trends data for {len(companies)} companies...")
    df = fetch_trends_for_all(companies)

    output_path = Path(behavioural_dir) / "trends.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Google Trends data saved to {output_path}")
    logger.info("Google Trends data saved to %s", output_path)

    return df
