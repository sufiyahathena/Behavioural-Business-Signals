"""Reddit brand sentiment collector.

Uses PRAW (Python Reddit API Wrapper) to search relevant subreddits for brand
mentions and applies VADER sentiment analysis to compute a per-company sentiment
score. Targets subreddits such as r/beauty, r/MakeupAddiction, r/SkincareAddiction,
r/femalefashionadvice, r/malefashionadvice, r/running, r/lululemon, etc.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import praw

logger = logging.getLogger(__name__)


def connect_reddit(client_id: str, client_secret: str, user_agent: str) -> praw.Reddit:
    """Initialise and return an authenticated PRAW Reddit instance.

    Args:
        client_id: Reddit app client ID from config.REDDIT_CLIENT_ID.
        client_secret: Reddit app client secret from config.REDDIT_CLIENT_SECRET.
        user_agent: Identifying string for the API request from config.REDDIT_USER_AGENT.

    Returns:
        Authenticated praw.Reddit instance in read-only mode.
    """
    # TODO: return praw.Reddit(client_id=client_id, client_secret=client_secret,
    # user_agent=user_agent) with read_only=True.
    pass


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
    # TODO: for each subreddit in subreddits, call reddit.subreddit(sub).search(
    # brand_name, limit=limit); extract title, selftext, score, subreddit.display_name;
    # collect into a flat list and return.
    pass


def compute_sentiment_score(mentions: list) -> float:
    """Compute a normalised sentiment score from a list of Reddit post dicts.

    Uses VADER SentimentIntensityAnalyzer on the concatenated title + selftext
    of each post. Returns the mean compound score mapped from [-1, 1] to [0, 1].

    Args:
        mentions: List of post dicts returned by fetch_brand_mentions.

    Returns:
        Sentiment score in [0, 1]. Returns 0.5 (neutral) if mentions list is empty.
    """
    # TODO: import vaderSentiment; instantiate SentimentIntensityAnalyzer;
    # for each mention compute compound score on (title + " " + selftext);
    # return (mean_compound + 1) / 2 to map [-1,1] -> [0,1]; handle empty list.
    pass


def fetch_all_companies(reddit: praw.Reddit, companies: list) -> pd.DataFrame:
    """Fetch Reddit sentiment scores for all companies.

    Args:
        reddit: Authenticated praw.Reddit instance.
        companies: List of company dicts with "ticker" and "name" keys.

    Returns:
        DataFrame with columns: ticker, company_name, reddit_sentiment.
    """
    # TODO: define a mapping of ticker -> list of relevant subreddits;
    # iterate over companies; call fetch_brand_mentions then compute_sentiment_score;
    # build results list; return pd.DataFrame(results).
    pass
