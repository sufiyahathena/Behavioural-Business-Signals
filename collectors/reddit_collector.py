"""Reddit brand sentiment collector.

Uses PRAW (Python Reddit API Wrapper) to search relevant subreddits for brand
mentions and applies VADER sentiment analysis to compute a per-company sentiment
score. Targets subreddits such as r/beauty, r/MakeupAddiction, r/SkincareAddiction,
r/femalefashionadvice, r/malefashionadvice, r/running, r/lululemon, etc.
"""

import logging
import time
from pathlib import Path

import pandas as pd
import praw
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import config

logger = logging.getLogger(__name__)

BRAND_SEARCH_TERMS = {
    "EL":    "Estee Lauder",
    "ULTA":  "Ulta Beauty",
    "ELF":   "elf cosmetics",
    "COTY":  "Coty beauty",
    "OLPX":  "Olaplex",
    "SBH":   "Sally Beauty",
    "ODD":   "Oddity Tech",
    "LRLCY": "L'Oreal",
    "ANF":   "Abercrombie Fitch",
    "AEO":   "American Eagle",
    "URBN":  "Urban Outfitters",
    "GAP":   "Gap clothing",
    "LEVI":  "Levis jeans",
    "RVLV":  "Revolve clothing",
    "LULU":  "Lululemon",
    "ONON":  "On Running shoes",
    "RL":    "Ralph Lauren",
    "COLM":  "Columbia Sportswear",
    "BIRK":  "Birkenstock",
}

# Subreddits most likely to surface authentic brand sentiment per company
SUBREDDITS_BY_TICKER = {
    "EL":    ["beauty", "MakeupAddiction", "SkincareAddiction", "femalefashionadvice"],
    "ULTA":  ["beauty", "MakeupAddiction", "SkincareAddiction", "Ulta"],
    "ELF":   ["beauty", "MakeupAddiction", "SkincareAddiction", "drugstorebeauty"],
    "COTY":  ["beauty", "MakeupAddiction", "SkincareAddiction"],
    "OLPX":  ["HaircareScience", "femalehairadvice", "beauty"],
    "SBH":   ["beauty", "MakeupAddiction", "HaircareScience"],
    "ODD":   ["beauty", "SkincareAddiction", "MakeupAddiction"],
    "LRLCY": ["beauty", "MakeupAddiction", "SkincareAddiction"],
    "ANF":   ["femalefashionadvice", "malefashionadvice", "streetwear"],
    "AEO":   ["femalefashionadvice", "malefashionadvice"],
    "URBN":  ["femalefashionadvice", "malefashionadvice", "streetwear"],
    "GAP":   ["femalefashionadvice", "malefashionadvice"],
    "LEVI":  ["femalefashionadvice", "malefashionadvice", "streetwear", "denim"],
    "RVLV":  ["femalefashionadvice", "streetwear"],
    "LULU":  ["lululemon", "running", "Fitness", "femalefashionadvice"],
    "ONON":  ["running", "trailrunning", "Fitness"],
    "RL":    ["femalefashionadvice", "malefashionadvice", "streetwear"],
    "COLM":  ["hiking", "camping", "Ultralight", "running"],
    "BIRK":  ["femalefashionadvice", "malefashionadvice", "streetwear"],
}


def connect_reddit(client_id: str, client_secret: str, user_agent: str) -> praw.Reddit:
    """Initialise and return an authenticated PRAW Reddit instance.

    Args:
        client_id: Reddit app client ID from config.REDDIT_CLIENT_ID.
        client_secret: Reddit app client secret from config.REDDIT_CLIENT_SECRET.
        user_agent: Identifying string for the API request from config.REDDIT_USER_AGENT.

    Returns:
        Authenticated praw.Reddit instance in read-only mode.
    """
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def fetch_brand_mentions(
    reddit: praw.Reddit,
    brand_name: str,
    subreddits: list,
    limit: int = 100,
) -> list:
    """Search a list of subreddits for posts mentioning a brand name.

    Args:
        reddit: Authenticated praw.Reddit instance.
        brand_name: Search term (company or brand name).
        subreddits: List of subreddit names to search (without the r/ prefix).
        limit: Maximum number of posts to retrieve per subreddit.

    Returns:
        List of dicts, each with keys: "title", "selftext", "score", "subreddit".
    """
    mentions = []
    for sub in subreddits:
        try:
            results = reddit.subreddit(sub).search(
                brand_name, limit=limit, sort="relevance", time_filter="year"
            )
            for post in results:
                mentions.append({
                    "title": post.title,
                    "selftext": post.selftext,
                    "score": post.score,
                    "subreddit": post.subreddit.display_name,
                })
            time.sleep(1)
        except Exception as e:
            logger.warning("Failed to search r/%s for '%s': %s", sub, brand_name, e)
    return mentions


def compute_sentiment_score(mentions: list) -> float:
    """Compute a normalised sentiment score from a list of Reddit post dicts.

    Uses VADER SentimentIntensityAnalyzer on the concatenated title + selftext
    of each post. Returns the mean compound score mapped from [-1, 1] to [0, 1].

    Args:
        mentions: List of post dicts returned by fetch_brand_mentions.

    Returns:
        Sentiment score in [0, 1]. Returns 0.5 (neutral) if mentions list is empty.
    """
    if not mentions:
        return 0.5

    analyser = SentimentIntensityAnalyzer()
    compounds = []
    for m in mentions:
        text = (m.get("title", "") + " " + m.get("selftext", "")).strip()
        if text:
            compound = analyser.polarity_scores(text)["compound"]
            compounds.append(compound)

    if not compounds:
        return 0.5

    mean_compound = sum(compounds) / len(compounds)
    return round((mean_compound + 1) / 2, 4)


def fetch_all_companies(reddit: praw.Reddit, companies: list) -> pd.DataFrame:
    """Fetch Reddit sentiment scores for all companies.

    Args:
        reddit: Authenticated praw.Reddit instance.
        companies: List of company dicts with "ticker" and "name" keys.

    Returns:
        DataFrame with columns: ticker, company_name, reddit_sentiment.
    """
    results = []
    for company in companies:
        ticker = company["ticker"]
        name = company["name"]
        keyword = BRAND_SEARCH_TERMS.get(ticker, name)
        subreddits = SUBREDDITS_BY_TICKER.get(ticker, ["beauty", "femalefashionadvice"])

        logger.info("Fetching Reddit sentiment for %s (%s)", ticker, keyword)
        print(f"  Fetching Reddit: {ticker} — {keyword} across {subreddits}")

        mentions = fetch_brand_mentions(reddit, keyword, subreddits)
        sentiment = compute_sentiment_score(mentions)
        print(f"    → {len(mentions)} posts found, sentiment score: {sentiment:.4f}")

        results.append({
            "ticker": ticker,
            "company_name": name,
            "reddit_sentiment": sentiment,
        })

    return pd.DataFrame(results)


def run(
    companies: list = None,
    behavioural_dir: str = config.BEHAVIOURAL_DIR,
    resume: bool = True,
) -> pd.DataFrame:
    """Run the Reddit sentiment collector and save results to CSV.

    If resume=True (default), skips companies that already have a non-null
    sentiment score in the existing reddit.csv.

    Args:
        companies: List of company dicts. If None, loads from companies.json.
        behavioural_dir: Directory to save reddit.csv output.
        resume: If True, skip companies already collected successfully.

    Returns:
        DataFrame with reddit_sentiment column.
    """
    import json

    if not config.REDDIT_CLIENT_ID or not config.REDDIT_CLIENT_SECRET:
        logger.error(
            "Reddit API credentials not set. "
            "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables."
        )
        return pd.DataFrame()

    if companies is None:
        companies_path = Path(config.DATA_DIR) / "companies.json"
        with companies_path.open() as f:
            companies = json.load(f)["companies"]

    output_path = Path(behavioural_dir) / "reddit.csv"

    existing_df = pd.DataFrame()
    already_done = set()
    if resume and output_path.exists():
        existing_df = pd.read_csv(output_path)
        if "reddit_sentiment" in existing_df.columns:
            done_mask = existing_df["reddit_sentiment"].notna()
            already_done = set(existing_df[done_mask]["ticker"].tolist())
            print(f"Resuming — {len(already_done)} companies already collected: {sorted(already_done)}")

    remaining = [c for c in companies if c["ticker"] not in already_done]
    print(f"Collecting Reddit sentiment for {len(remaining)} remaining companies...")

    if not remaining:
        print("All companies already collected!")
        return existing_df

    reddit = connect_reddit(
        config.REDDIT_CLIENT_ID,
        config.REDDIT_CLIENT_SECRET,
        config.REDDIT_USER_AGENT,
    )
    new_df = fetch_all_companies(reddit, remaining)

    if not existing_df.empty and already_done:
        done_df = existing_df[existing_df["ticker"].isin(already_done)]
        combined_df = pd.concat([done_df, new_df], ignore_index=True)
        ticker_order = [c["ticker"] for c in companies]
        combined_df["_order"] = combined_df["ticker"].map(
            {t: i for i, t in enumerate(ticker_order)}
        )
        combined_df = combined_df.sort_values("_order").drop(columns=["_order"])
    else:
        combined_df = new_df

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)
    print(f"Reddit sentiment data saved to {output_path}")
    logger.info("Reddit sentiment data saved to %s", output_path)

    return combined_df
