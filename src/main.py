"""
Daily News Digest - Main Orchestrator
Ties together feed fetching, categorization, formatting, and email delivery.

Usage:
    python -m src.main digest    # Full morning digest (last 24h)
    python -m src.main update    # Intraday update (last 6h)
    python -m src.main test      # Dry run - prints to console, no email sent
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from .categorizer import categorize_articles
from .emailer import send_email
from .feeds import fetch_all_feeds, filter_by_time
from .formatter import build_html_email, build_plain_text_email
from .ranker import rank_stories
from .site_builder import write_site

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.yaml."""
    # Look for config.yaml relative to this file's parent directory
    config_path = Path(__file__).parent.parent / "config.yaml"

    if not config_path.exists():
        # Also check current working directory
        config_path = Path("config.yaml")

    if not config_path.exists():
        logger.error(f"Config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded config with {len(config['feeds'])} feeds and {len(config['topics'])} topics")
    return config


def run_digest(config: dict, dry_run: bool = False) -> bool:
    """
    Run the full morning digest.

    Fetches articles from the last 24 hours, categorizes them,
    formats into an email, and sends it.

    Args:
        config: Loaded configuration dictionary.
        dry_run: If True, print output instead of sending email.

    Returns:
        True if successful.
    """
    settings = config["settings"]
    lookback = settings.get("lookback_hours_digest", 24)
    max_per_topic = settings.get("max_articles_per_topic", 10)

    logger.info(f"Running morning digest (lookback: {lookback}h)")

    # Fetch all feeds
    articles = fetch_all_feeds(config["feeds"])

    if not articles:
        logger.warning("No articles fetched from any feed")
        return False

    # Filter by time
    articles = filter_by_time(articles, hours=lookback)

    if not articles:
        logger.warning(f"No articles found in the last {lookback} hours")
        return False

    # Categorize
    categorized = categorize_articles(articles, config["topics"])

    # Format
    subject, html_body = build_html_email(
        categorized, config["topics"], mode="digest", max_per_topic=max_per_topic
    )
    plain_text = build_plain_text_email(
        categorized, config["topics"], mode="digest", max_per_topic=max_per_topic
    )

    if dry_run:
        print(f"\n{'='*60}")
        print(f"SUBJECT: {subject}")
        print(f"{'='*60}")
        print(plain_text)
        print(f"\n{'='*60}")
        print("(Dry run - email not sent)")
        print(f"HTML body length: {len(html_body)} chars")
        return True

    # Send
    return send_email(subject, html_body, plain_text)


def run_update(config: dict, dry_run: bool = False) -> bool:
    """
    Run an intraday update.

    Fetches articles from the last 6 hours, categorizes them,
    formats a shorter update email, and sends it.

    Args:
        config: Loaded configuration dictionary.
        dry_run: If True, print output instead of sending email.

    Returns:
        True if successful.
    """
    settings = config["settings"]
    lookback = settings.get("lookback_hours_update", 6)
    max_per_topic = settings.get("max_articles_per_update", 5)

    logger.info(f"Running intraday update (lookback: {lookback}h)")

    # Fetch all feeds
    articles = fetch_all_feeds(config["feeds"])

    if not articles:
        logger.warning("No articles fetched from any feed")
        return False

    # Filter by time (shorter window for updates)
    articles = filter_by_time(articles, hours=lookback)

    if not articles:
        logger.info(f"No new articles in the last {lookback} hours - skipping update")
        return True  # Not a failure, just nothing new

    # Categorize
    categorized = categorize_articles(articles, config["topics"])

    # Format
    subject, html_body = build_html_email(
        categorized, config["topics"], mode="update", max_per_topic=max_per_topic
    )
    plain_text = build_plain_text_email(
        categorized, config["topics"], mode="update", max_per_topic=max_per_topic
    )

    if dry_run:
        print(f"\n{'='*60}")
        print(f"SUBJECT: {subject}")
        print(f"{'='*60}")
        print(plain_text)
        print(f"\n{'='*60}")
        print("(Dry run - email not sent)")
        print(f"HTML body length: {len(html_body)} chars")
        return True

    # Send
    return send_email(subject, html_body, plain_text)


def run_build(config: dict, output_dir: str = "public") -> bool:
    """
    Build the static web dashboard.

    Pipeline: fetch -> time-filter -> rank (cluster + score across sources)
    -> categorize the representative stories -> write an HTML dashboard with a
    Top Stories hero and importance-ranked topic sections.

    Args:
        config: Loaded configuration dictionary.
        output_dir: Directory to write the site into.

    Returns:
        True if successful.
    """
    settings = config["settings"]
    ranking = config.get("ranking", {})
    lookback = settings.get("lookback_hours_digest", 24)
    max_per_topic = settings.get("max_articles_per_topic", 25)
    top_stories_count = ranking.get("top_stories_count", 8)
    preview_per_topic = ranking.get("preview_per_topic", 5)

    logger.info(f"Building dashboard (lookback: {lookback}h) -> {output_dir}/")

    # Fetch all feeds
    articles = fetch_all_feeds(config["feeds"])

    if not articles:
        logger.warning("No articles fetched from any feed")
        return False

    # Filter by time
    articles = filter_by_time(articles, hours=lookback)

    if not articles:
        logger.warning(f"No articles found in the last {lookback} hours")
        return False

    # Rank: cluster near-duplicate stories across sources and score by
    # importance. Collapses duplicates to one representative per story.
    stories = rank_stories(articles, config)

    # Categorize the ranked representative stories.
    categorized = categorize_articles(stories, config["topics"])

    # Tag each story with its topic (used by the Top Stories hero) and
    # re-sort each topic bucket by importance score (categorizer sorts by date).
    for topic_name, topic_articles in categorized.items():
        for article in topic_articles:
            article.topic = topic_name
        topic_articles.sort(key=lambda a: a.score, reverse=True)

    # Top Stories hero = highest-scoring stories across all topics.
    top_stories = stories[:top_stories_count]

    # Build the site
    write_site(
        categorized,
        config["topics"],
        output_dir=output_dir,
        max_per_topic=max_per_topic,
        top_stories=top_stories,
        preview_per_topic=preview_per_topic,
    )

    return True


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Daily News Digest - Fetches, categorizes, and publishes news updates"
    )
    parser.add_argument(
        "mode",
        choices=["digest", "update", "test", "build"],
        help=(
            "digest: Full morning digest email (24h lookback). "
            "update: Intraday update email (6h lookback). "
            "test: Dry run, prints to console without sending email. "
            "build: Generate the static web dashboard into ./public."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to console instead of sending email.",
    )
    parser.add_argument(
        "--output",
        default="public",
        help="Output directory for build mode (default: public).",
    )

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Determine if dry run
    dry_run = args.dry_run or args.mode == "test"

    # Run appropriate mode
    if args.mode == "build":
        success = run_build(config, output_dir=args.output)
    elif args.mode in ("digest", "test"):
        success = run_digest(config, dry_run=dry_run)
    else:
        success = run_update(config, dry_run=dry_run)

    if success:
        logger.info("Completed successfully")
        sys.exit(0)
    else:
        logger.error("Failed to complete")
        sys.exit(1)


if __name__ == "__main__":
    main()
