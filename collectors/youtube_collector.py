"""YouTube Data API collector.

Fetches subscriber count for each company's primary YouTube channel.
Uses channel handles/usernames which are more stable than channel IDs.
Requires YOUTUBE_API_KEY environment variable.
"""

import logging
import time
from pathlib import Path

import pandas as pd
import numpy as np
import requests

import config

logger = logging.getLogger(__name__)

# YouTube channel handles or forUsername values
# Format: ("handle", "type") where type is "handle" or "user"
YOUTUBE_CHANNELS = {
    "EL":    ("esteelauder", "handle"),
    "ULTA":  ("ultabeauty", "handle"),
    "ELF":   ("elfcosmetics", "handle"),
    "COTY":  ("covergirl", "user"),
    "OLPX":  ("olaplex", "handle"),
    "SBH":   ("SallyBeautySupply", "user"),
    "ODD":   ("ilmakiage", "handle"),
    "LRLCY": ("LOrealParis", "user"),
    "ANF":   ("abercrombie", "handle"),
    "AEO":   ("americaneagle", "handle"),
    "URBN":  ("urbanoutfitters", "handle"),
    "GAP":   ("gap", "handle"),
    "LEVI":  ("levis", "handle"),
    "RVLV":  ("revolve", "handle"),
    "LULU":  ("lululemon", "handle"),
    "ONON":  ("UCYp6nZ3yx11axEaq9STzdkg", "id"),
    "RL":    ("RalphLauren", "handle"),
    "COLM":  ("columbiasportswear", "handle"),
    "BIRK":  ("BIRKENSTOCKtv", "handle"),
}


def fetch_channel_stats(channel_info: tuple) -> dict:
    """Fetch subscriber count for a YouTube channel by handle or username.

    Args:
        channel_info: Tuple of (name, type) where type is "handle" or "user".

    Returns:
        Dict with subscriber_count, or 0 on failure.
    """
    if not config.YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY not set")
        return {"subscriber_count": 0}

    name, lookup_type = channel_info
    url = "https://www.googleapis.com/youtube/v3/channels"

    if lookup_type == "handle":
        params = {
            "part": "statistics",
            "forHandle": name,
            "key": config.YOUTUBE_API_KEY,
        }
    elif lookup_type == "id":
        params = {
            "part": "statistics",
            "id": name,
            "key": config.YOUTUBE_API_KEY,
        }
    else:
        params = {
            "part": "statistics",
            "forUsername": name,
            "key": config.YOUTUBE_API_KEY,
        }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            logger.warning("No channel found for %s: %s", lookup_type, name)
            return {"subscriber_count": 0}

        stats = items[0].get("statistics", {})
        return {
            "subscriber_count": int(stats.get("subscriberCount", 0)),
        }
    except Exception as e:
        logger.error("Failed to fetch YouTube stats for %s: %s", name, e)
        return {"subscriber_count": 0}


def fetch_all_companies(companies: list) -> pd.DataFrame:
    """Fetch YouTube subscriber counts for all companies."""
    results = []
    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        channel_info = YOUTUBE_CHANNELS.get(ticker)

        if channel_info is None:
            print(f"  {ticker} — no YouTube channel, skipping")
            results.append({
                "ticker": ticker,
                "company_name": name,
                "youtube_subscribers": np.nan,
            })
            continue

        print(f"  Fetching YouTube stats: {ticker} — @{channel_info[0]}")
        stats = fetch_channel_stats(channel_info)
        sub_count = stats["subscriber_count"] if stats["subscriber_count"] > 0 else np.nan

        results.append({
            "ticker": ticker,
            "company_name": name,
            "youtube_subscribers": sub_count,
        })
        time.sleep(0.5)

    return pd.DataFrame(results)


def run(
    companies: list = None,
    behavioural_dir: str = config.BEHAVIOURAL_DIR,
) -> pd.DataFrame:
    """Run the YouTube collector and save results to CSV."""
    import json

    if companies is None:
        companies_path = Path(config.DATA_DIR) / "companies.json"
        with companies_path.open() as f:
            companies = json.load(f)["companies"]

    print(f"Collecting YouTube data for {len(companies)} companies...")
    df = fetch_all_companies(companies)

    output_path = Path(behavioural_dir) / "youtube.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"YouTube data saved to {output_path}")

    rated = df[df["youtube_subscribers"].notna()]
    print(f"\nData collected for {len(rated)}/{len(df)} companies:")
    for _, row in rated.iterrows():
        subs = f"{int(row['youtube_subscribers']):,}"
        print(f"  {row['ticker']}: {subs} subscribers")

    return df
