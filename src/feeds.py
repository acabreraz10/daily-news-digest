"""
RSS Feed Fetcher
Fetches articles from configured RSS feeds with deduplication and error handling.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import feedparser
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents a single news article."""
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    default_topic: str
    language: str = "en"
    article_id: str = field(default="", repr=False)

    def __post_init__(self):
        if not self.article_id:
            # Generate a unique ID based on title + link for deduplication
            content = f"{self.title}{self.link}".encode("utf-8")
            self.article_id = hashlib.md5(content).hexdigest()

    def __eq__(self, other):
        if not isinstance(other, Article):
            return False
        return self.article_id == other.article_id

    def __hash__(self):
        return hash(self.article_id)


def parse_date(date_string: Optional[str]) -> datetime:
    """Parse a date string from an RSS feed into a datetime object."""
    if not date_string:
        return datetime.now(timezone.utc)
    try:
        dt = dateparser.parse(date_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def clean_summary(summary: str, max_length: int = 300) -> str:
    """Clean HTML tags from summary and truncate."""
    import re
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", summary)
    # Remove extra whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate
    if len(clean) > max_length:
        clean = clean[:max_length].rsplit(" ", 1)[0] + "..."
    return clean


def fetch_feed(feed_config: dict) -> list[Article]:
    """
    Fetch articles from a single RSS feed.

    Args:
        feed_config: Dictionary with keys: name, url, language, default_topic

    Returns:
        List of Article objects from this feed.
    """
    name = feed_config["name"]
    url = feed_config["url"]
    language = feed_config.get("language", "en")
    default_topic = feed_config.get("default_topic", "World News")

    logger.info(f"Fetching feed: {name} ({url})")

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Feed error for {name}: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            summary = entry.get("summary", entry.get("description", ""))
            summary = clean_summary(summary)

            published = parse_date(
                entry.get("published", entry.get("updated", None))
            )

            article = Article(
                title=title,
                link=link,
                summary=summary,
                published=published,
                source=name,
                default_topic=default_topic,
                language=language,
            )
            articles.append(article)

        logger.info(f"Fetched {len(articles)} articles from {name}")
        return articles

    except Exception as e:
        logger.error(f"Failed to fetch feed {name}: {e}")
        return []


def fetch_all_feeds(feeds_config: list[dict]) -> list[Article]:
    """
    Fetch articles from all configured feeds with deduplication.

    Args:
        feeds_config: List of feed configuration dictionaries.

    Returns:
        Deduplicated list of Article objects, sorted by publish date (newest first).
    """
    all_articles: dict[str, Article] = {}

    for feed_config in feeds_config:
        articles = fetch_feed(feed_config)
        for article in articles:
            # Deduplication: keep the first occurrence (by article_id)
            if article.article_id not in all_articles:
                all_articles[article.article_id] = article

    # Sort by published date, newest first
    sorted_articles = sorted(
        all_articles.values(),
        key=lambda a: a.published,
        reverse=True,
    )

    logger.info(
        f"Total unique articles fetched: {len(sorted_articles)} "
        f"(from {len(feeds_config)} feeds)"
    )
    return sorted_articles


def filter_by_time(articles: list[Article], hours: int) -> list[Article]:
    """
    Filter articles to only include those published within the last N hours.

    Args:
        articles: List of articles to filter.
        hours: Number of hours to look back.

    Returns:
        Filtered list of articles.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = [a for a in articles if a.published >= cutoff]

    logger.info(
        f"Filtered to {len(filtered)} articles from last {hours} hours "
        f"(out of {len(articles)} total)"
    )
    return filtered
