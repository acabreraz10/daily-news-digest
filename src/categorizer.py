"""
Article Categorizer
Groups articles by topic using feed source defaults and keyword matching.
"""

import logging
from dataclasses import dataclass

from .feeds import Article

logger = logging.getLogger(__name__)


@dataclass
class TopicConfig:
    """Configuration for a single topic category."""
    name: str
    icon: str
    keywords: list[str]


def build_topic_configs(topics_config: list[dict]) -> list[TopicConfig]:
    """Convert raw topic config dicts into TopicConfig objects."""
    return [
        TopicConfig(
            name=t["name"],
            icon=t.get("icon", ""),
            keywords=[kw.lower() for kw in t.get("keywords", [])],
        )
        for t in topics_config
    ]


def score_article_for_topic(article: Article, topic: TopicConfig) -> int:
    """
    Score how well an article matches a topic based on keyword presence.

    Checks title (higher weight) and summary (lower weight) for keyword matches.

    Returns:
        Integer score. Higher means better match.
    """
    score = 0
    title_lower = article.title.lower()
    summary_lower = article.summary.lower()

    for keyword in topic.keywords:
        if keyword in title_lower:
            score += 3  # Title matches are worth more
        if keyword in summary_lower:
            score += 1

    return score


def categorize_article(article: Article, topics: list[TopicConfig]) -> str:
    """
    Determine the best topic for an article.

    Strategy:
    1. Score the article against all topics using keyword matching.
    2. If the best score is > 0, assign to the highest-scoring topic.
    3. Otherwise, fall back to the feed's default_topic.

    Args:
        article: The article to categorize.
        topics: List of topic configurations.

    Returns:
        The topic name (string) that best fits the article.
    """
    best_topic = article.default_topic
    best_score = 0

    for topic in topics:
        score = score_article_for_topic(article, topic)
        if score > best_score:
            best_score = score
            best_topic = topic.name

    return best_topic


def categorize_articles(
    articles: list[Article],
    topics_config: list[dict],
) -> dict[str, list[Article]]:
    """
    Categorize all articles into topic groups.

    Args:
        articles: List of articles to categorize.
        topics_config: Raw topic configuration from config.yaml.

    Returns:
        Dictionary mapping topic name -> list of articles, ordered by
        the topic order in config. Only topics with articles are included.
    """
    topics = build_topic_configs(topics_config)

    # Initialize result dict in config order
    categorized: dict[str, list[Article]] = {}
    topic_order = [t.name for t in topics]

    for article in articles:
        topic_name = categorize_article(article, topics)
        if topic_name not in categorized:
            categorized[topic_name] = []
        categorized[topic_name].append(article)

    # Sort each topic's articles by publish date (newest first)
    for topic_name in categorized:
        categorized[topic_name].sort(key=lambda a: a.published, reverse=True)

    # Reorder dict to match config topic order
    ordered: dict[str, list[Article]] = {}
    for name in topic_order:
        if name in categorized:
            ordered[name] = categorized[name]
    # Add any articles that ended up in topics not in the config order
    for name, articles_list in categorized.items():
        if name not in ordered:
            ordered[name] = articles_list

    total = sum(len(v) for v in ordered.values())
    logger.info(
        f"Categorized {total} articles into {len(ordered)} topics: "
        f"{', '.join(f'{k} ({len(v)})' for k, v in ordered.items())}"
    )

    return ordered


def get_topic_icon(topic_name: str, topics_config: list[dict]) -> str:
    """Get the emoji icon for a topic name."""
    for t in topics_config:
        if t["name"] == topic_name:
            return t.get("icon", "")
    return ""
