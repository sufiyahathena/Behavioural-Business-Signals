"""Trustpilot consumer rating collector.

Scrapes each company's Trustpilot page to extract the overall star rating and
total review count. These are used as consumer satisfaction and review volume
signals in the behavioural score.

Note: Trustpilot does not have an official public API for free use. This collector
uses BeautifulSoup to parse the public HTML. Check Trustpilot's terms of service
before using in production.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TRUSTPILOT_BASE_URL = "https://www.trustpilot.com/review/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_trustpilot_data(company_url_slug: str) -> dict:
    """Fetch the Trustpilot rating and review count for a single company.

    Args:
        company_url_slug: The Trustpilot URL slug for the company
            (e.g. "www.ulta.com" or "elfcosmetics.com").

    Returns:
        Dict with keys: "slug", "trustpilot_rating" (float), "trustpilot_review_count" (int).
        Returns zeroed dict on failure.
    """
    # TODO: build URL from TRUSTPILOT_BASE_URL + company_url_slug; GET request
    # with HEADERS; pass HTML to parse_rating_and_count; return result dict
    # with error handling (return {"slug": company_url_slug, "trustpilot_rating": 0.0,
    # "trustpilot_review_count": 0} on any exception).
    pass


def parse_rating_and_count(html: str) -> tuple:
    """Parse a Trustpilot review page HTML to extract rating and review count.

    Args:
        html: Raw HTML string of a Trustpilot company review page.

    Returns:
        Tuple of (rating: float, review_count: int). Returns (0.0, 0) on parse failure.
    """
    # TODO: parse with BeautifulSoup(html, "html.parser"); locate the
    # <script type="application/ld+json"> tag containing aggregateRating;
    # extract ratingValue and reviewCount; return (float(rating), int(count)).
    pass


def fetch_all_companies(companies: list) -> pd.DataFrame:
    """Fetch Trustpilot data for all companies.

    Args:
        companies: List of dicts with "ticker", "name", and "trustpilot_slug" keys.
            The trustpilot_slug must be added to companies.json or passed separately.

    Returns:
        DataFrame with columns: ticker, company_name, trustpilot_rating, trustpilot_review_count.
    """
    # TODO: iterate over companies; call fetch_trustpilot_data; sleep 2s between
    # requests to be polite; collect results; return pd.DataFrame(results).
    pass
