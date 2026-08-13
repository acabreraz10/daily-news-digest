"""
Email Formatter
Builds clean, responsive HTML emails for the news digest.
"""

import logging
from datetime import datetime

from .categorizer import get_topic_icon
from .feeds import Article

logger = logging.getLogger(__name__)


def format_time_ago(published: datetime) -> str:
    """Format a datetime as a human-readable 'time ago' string."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    delta = now - published

    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}m ago"
    elif hours < 24:
        return f"{hours}h ago"
    else:
        days = int(hours / 24)
        return f"{days}d ago"


def build_html_email(
    categorized_articles: dict[str, list[Article]],
    topics_config: list[dict],
    mode: str = "digest",
    max_per_topic: int = 10,
) -> tuple[str, str]:
    """
    Build a formatted HTML email from categorized articles.

    Args:
        categorized_articles: Dict of topic_name -> list of articles.
        topics_config: Raw topic config for icon lookup.
        mode: "digest" for morning full digest, "update" for intraday updates.
        max_per_topic: Maximum articles to show per topic section.

    Returns:
        Tuple of (subject_line, html_body).
    """
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")

    if mode == "digest":
        subject = f"Morning News Digest - {date_str}"
        header_text = "Good Morning! Here's Your Daily Digest"
        subtitle = f"Top stories for {date_str}"
    else:
        time_str = now.strftime("%I:%M %p")
        subject = f"News Update - {time_str} {date_str}"
        header_text = "News Update"
        subtitle = f"Latest stories as of {time_str}"

    total_articles = sum(len(v) for v in categorized_articles.values())

    # Build topic sections
    topic_sections = ""
    for topic_name, articles in categorized_articles.items():
        icon = get_topic_icon(topic_name, topics_config)
        display_articles = articles[:max_per_topic]

        articles_html = ""
        for article in display_articles:
            time_ago = format_time_ago(article.published)
            source_badge = article.source

            articles_html += f"""
            <tr>
              <td style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
                <a href="{article.link}" style="color: #1a1a1a; text-decoration: none; font-size: 15px; font-weight: 600; line-height: 1.4;">
                  {article.title}
                </a>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 13px; line-height: 1.5;">
                  {article.summary}
                </p>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #999;">
                  <span style="background: #f5f5f5; padding: 2px 8px; border-radius: 3px; margin-right: 8px;">{source_badge}</span>
                  {time_ago}
                </p>
              </td>
            </tr>"""

        remaining = len(articles) - max_per_topic
        more_html = ""
        if remaining > 0:
            more_html = f"""
            <tr>
              <td style="padding: 8px 0; color: #999; font-size: 13px; font-style: italic;">
                + {remaining} more stories in this category
              </td>
            </tr>"""

        topic_sections += f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
          <tr>
            <td style="padding: 12px 16px; background: #f8f9fa; border-radius: 8px 8px 0 0; border-left: 4px solid #2563eb;">
              <span style="font-size: 18px; font-weight: 700; color: #1a1a1a;">
                {icon} {topic_name}
              </span>
              <span style="float: right; color: #999; font-size: 13px;">{len(display_articles)} stories</span>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 16px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {articles_html}
                {more_html}
              </table>
            </td>
          </tr>
        </table>
        """

    # Full HTML email
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%); padding: 32px 24px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">{header_text}</h1>
              <p style="margin: 8px 0 0 0; color: #bfdbfe; font-size: 14px;">{subtitle}</p>
            </td>
          </tr>

          <!-- Summary bar -->
          <tr>
            <td style="padding: 16px 24px; background: #eff6ff; border-bottom: 1px solid #e5e7eb;">
              <span style="font-size: 13px; color: #1e40af; font-weight: 600;">
                {total_articles} articles across {len(categorized_articles)} topics
              </span>
            </td>
          </tr>

          <!-- Content -->
          <tr>
            <td style="padding: 24px;">
              {topic_sections}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 24px; background: #f9fafb; border-top: 1px solid #e5e7eb; text-align: center;">
              <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                Daily News Digest &bull; Auto-generated from RSS feeds<br>
                Delivered at {now.strftime("%I:%M %p %Z")} on {date_str}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    logger.info(
        f"Formatted {mode} email: '{subject}' with {total_articles} articles "
        f"across {len(categorized_articles)} topics"
    )

    return subject, html


def build_plain_text_email(
    categorized_articles: dict[str, list[Article]],
    topics_config: list[dict],
    mode: str = "digest",
    max_per_topic: int = 10,
) -> str:
    """
    Build a plain-text fallback version of the email.

    Args:
        categorized_articles: Dict of topic_name -> list of articles.
        topics_config: Raw topic config for icon lookup.
        mode: "digest" or "update".
        max_per_topic: Maximum articles per topic.

    Returns:
        Plain text string.
    """
    now = datetime.now()
    date_str = now.strftime("%B %d, %Y")

    if mode == "digest":
        header = f"MORNING NEWS DIGEST - {date_str}"
    else:
        time_str = now.strftime("%I:%M %p")
        header = f"NEWS UPDATE - {time_str} {date_str}"

    lines = [header, "=" * len(header), ""]

    for topic_name, articles in categorized_articles.items():
        icon = get_topic_icon(topic_name, topics_config)
        lines.append(f"{icon} {topic_name}")
        lines.append("-" * 40)

        for article in articles[:max_per_topic]:
            time_ago = format_time_ago(article.published)
            lines.append(f"  * {article.title}")
            lines.append(f"    {article.source} | {time_ago}")
            lines.append(f"    {article.link}")
            if article.summary:
                lines.append(f"    {article.summary[:150]}")
            lines.append("")

        lines.append("")

    return "\n".join(lines)
