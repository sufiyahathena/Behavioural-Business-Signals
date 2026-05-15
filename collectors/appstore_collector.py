"""App Store and Google Play rating collector.

Reads app IDs from a manual CSV and fetches live ratings from Google Play Store.
App rating is used as a proxy for digital product quality and consumer satisfaction
with the brand's digital experience. Companies without apps receive NaN which the
scorer handles via median fallback.
"""

import logging
import time
from pathlib import Path

import pandas as pd
import numpy as np

import config

logger = logging.getLogger(__name__)

# Google Play Store app IDs for each company
# None = company has no relevant consumer app
ANDROID_APP_IDS = {
    "EL":    None,                           # Estée Lauder — no single consumer app (brand apps only e.g. MAC, Clinique)
    "ULTA":  "com.ulta",                     # Ulta Beauty: Makeup & Skincare
    "ELF":   "com.elfcosmetics.elfbeauty",   # e.l.f. Beauty
    "COTY":  None,                           # Coty — no single consumer app
    "OLPX":  None,                           # Olaplex — no consumer app
    "SBH":   "com.sallybeauty.app",          # Sally Beauty
    "ODD":   None,                           # Oddity Tech — no single consumer app
    "LRLCY": None,                           # L'Oréal — no single global consumer app
    "ANF":   "com.abercrombie.abercrombie",  # Abercrombie & Fitch
    "AEO":   "com.ae.americaneagle",         # American Eagle
    "URBN":  "com.urbanoutfitters.android",  # Urban Outfitters
    "GAP":   "com.gap.android",              # Gap
    "LEVI":  "com.levi.levis247",            # Levi's
    "RVLV":  "com.revolve",                  # REVOLVE
    "LULU":  None,                           # Lululemon — no fetchable consumer app
    "ONON":  "com.on_running.onrunning",     # On Running
    "RL":    "com.ralphlauren.ralphlauren",  # Ralph Lauren
    "COLM":  None,                           # Columbia Sportswear — no fetchable consumer app
    "BIRK":  None,                           # Birkenstock — no consumer app
}


def fetch_android_rating(app_id: str) -> float:
    """Fetch the current rating from the Google Play Store.

    Args:
        app_id: The Android package name (e.g. "com.ulta.beauty").

    Returns:
        Rating as float (1.0-5.0), or 0.0 on failure.
    """
    try:
        from google_play_scraper import app as gp_app
        result = gp_app(app_id, lang="en", country="us")
        score = result.get("score")
        if score and score > 0:
            return round(float(score), 2)
        return 0.0
    except Exception as e:
        logger.error("Failed to fetch Play Store rating for '%s': %s", app_id, e)
        return 0.0


def fetch_all_companies(companies: list) -> pd.DataFrame:
    """Fetch app ratings for all companies that have known app IDs.

    Args:
        companies: List of dicts with "ticker" and "name" keys.

    Returns:
        DataFrame with columns: ticker, company_name, app_rating.
    """
    results = []
    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        android_id = ANDROID_APP_IDS.get(ticker)

        if android_id is None:
            logger.info("%s — no app ID, skipping", ticker)
            print(f"  {ticker} — no app, skipping")
            results.append({
                "ticker": ticker,
                "company_name": name,
                "app_rating": np.nan,
            })
            continue

        print(f"  Fetching app rating: {ticker} — {android_id}")
        rating = fetch_android_rating(android_id)

        results.append({
            "ticker": ticker,
            "company_name": name,
            "app_rating": rating if rating > 0 else np.nan,
        })
        time.sleep(1)

    return pd.DataFrame(results)


def run(
    companies: list = None,
    behavioural_dir: str = config.BEHAVIOURAL_DIR,
) -> pd.DataFrame:
    """Run the App Store collector and save results to CSV.

    Args:
        companies: List of company dicts. If None, loads from companies.json.
        behavioural_dir: Directory to save appstore.csv output.

    Returns:
        DataFrame with app_rating for all companies.
    """
    import json

    if companies is None:
        companies_path = Path(config.DATA_DIR) / "companies.json"
        with companies_path.open() as f:
            companies = json.load(f)["companies"]

    print(f"Collecting app ratings for {len(companies)} companies...")
    df = fetch_all_companies(companies)

    output_path = Path(behavioural_dir) / "appstore.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"App ratings saved to {output_path}")
    logger.info("App ratings saved to %s", output_path)

    # Print summary
    rated = df[df["app_rating"].notna()]
    print(f"\nRatings collected for {len(rated)}/{len(df)} companies:")
    for _, row in rated.iterrows():
        print(f"  {row['ticker']}: {row['app_rating']}")

    return df
