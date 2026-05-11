"""news_collector.py

Fetches recent news articles for a company via Google News RSS feed.
No API key required. Uses feedparser to parse the RSS response.
"""

import logging
import re
from datetime import datetime

import feedparser

logger = logging.getLogger(__name__)


def fetch_company_news(
    company_name: str,
    ticker: str,
    max_articles: int = 8,
) -> list[dict]:
    """Fetch recent news articles for a company from Google News RSS.

    Args:
        company_name: Full company name (e.g. "Ulta Beauty").
        ticker: Stock ticker (e.g. "ULTA") — appended to query for precision.
        max_articles: Maximum number of articles to return (default 8).

    Returns:
        List of dicts, each containing:
            - title: article headline (source suffix stripped)
            - link: URL to full article
            - published: publication date as a human-readable string
            - published_parsed: datetime object or None
            - source: news source name extracted from Google News title
            - summary: always "" (Google News RSS summaries repeat the title)
    """
    QUERY_OVERRIDES = {
        "LRLCY": "L'Oréal beauty",
        "BIRK": "Birkenstock",
        "OLPX": "Olaplex hair",
        "ODD": "Oddity Tech beauty",
    }

    if ticker in QUERY_OVERRIDES:
        query = QUERY_OVERRIDES[ticker].replace(" ", "+")
    else:
        query = f"{company_name} {ticker}".replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("Failed to fetch news for %s: feed parse error", company_name)
            return []

        articles = []
        for entry in feed.entries[:max_articles]:
            # Google News formats titles as "Headline - Source Name"
            raw_title = entry.get("title", "")
            title_parts = raw_title.rsplit(" - ", 1)
            title = title_parts[0].strip() if len(title_parts) > 1 else raw_title
            source = title_parts[1].strip() if len(title_parts) > 1 else "Unknown source"
            # Remove stock ticker references appended by financial sites
            # e.g. "(OTCMKTS:LRLCY)", "(NYSE:EL)", "(NASDAQ:ULTA)", "(OTC:LRLCF)"
            title = re.sub(r'\s*\([A-Z]+:[A-Z]+\)', '', title).strip()

            published_parsed = None
            published_str = "Date unavailable"
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_parsed = datetime(*entry.published_parsed[:6])
                    published_str = published_parsed.strftime("%d %b %Y")
                except Exception:
                    pass

            articles.append({
                "title": title,
                "link": entry.get("link", "#"),
                "published": published_str,
                "published_parsed": published_parsed,
                "source": source,
                "summary": "",
            })

        logger.info("Fetched %d articles for %s", len(articles), company_name)
        return articles

    except Exception as e:
        logger.error("Error fetching news for %s: %s", company_name, e)
        return []
