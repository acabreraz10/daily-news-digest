"""
Static Site Builder
Generates a responsive HTML dashboard (+ PWA manifest) for the news digest.
Designed to be published on GitHub Pages.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .categorizer import get_topic_icon
from .feeds import Article

logger = logging.getLogger(__name__)


def format_time_ago(published: datetime) -> str:
    """Format a datetime as a human-readable 'time ago' string."""
    now = datetime.now(timezone.utc)
    delta = now - published
    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        minutes = max(0, int(delta.total_seconds() / 60))
        return f"{minutes}m ago"
    elif hours < 24:
        return f"{hours}h ago"
    else:
        days = int(hours / 24)
        return f"{days}d ago"


def build_nav(categorized: dict[str, list[Article]], topics_config: list[dict]) -> str:
    """Build the topic navigation chips."""
    chips = ""
    for topic_name in categorized:
        icon = get_topic_icon(topic_name, topics_config)
        anchor = topic_name.lower().replace(" ", "-").replace("&", "and")
        chips += (
            f'<a href="#{anchor}" class="chip">{icon} {topic_name}'
            f'<span class="chip-count">{len(categorized[topic_name])}</span></a>'
        )
    return chips


def build_topic_sections(
    categorized: dict[str, list[Article]],
    topics_config: list[dict],
    max_per_topic: int,
) -> str:
    """Build the main content sections, one per topic."""
    sections = ""
    for topic_name, articles in categorized.items():
        icon = get_topic_icon(topic_name, topics_config)
        anchor = topic_name.lower().replace(" ", "-").replace("&", "and")
        display = articles[:max_per_topic]

        cards = ""
        for a in display:
            time_ago = format_time_ago(a.published)
            summary = a.summary if a.summary else ""
            cards += f"""
          <a class="card" href="{a.link}" target="_blank" rel="noopener noreferrer">
            <div class="card-title">{a.title}</div>
            <div class="card-summary">{summary}</div>
            <div class="card-meta">
              <span class="source">{a.source}</span>
              <span class="time">{time_ago}</span>
            </div>
          </a>"""

        sections += f"""
      <section id="{anchor}" class="topic">
        <div class="topic-header">
          <h2>{icon} {topic_name}</h2>
          <span class="topic-count">{len(display)} stories</span>
        </div>
        <div class="cards">
          {cards}
        </div>
      </section>"""
    return sections


def build_dashboard_html(
    categorized: dict[str, list[Article]],
    topics_config: list[dict],
    max_per_topic: int = 15,
) -> str:
    """
    Build the complete HTML dashboard page.

    Args:
        categorized: Dict of topic_name -> list of articles.
        topics_config: Raw topic config for icon lookup.
        max_per_topic: Max articles to show per topic.

    Returns:
        Complete HTML string.
    """
    now = datetime.now(timezone.utc)
    # Convert to Pacific for display
    updated_str = now.strftime("%b %d, %Y at %H:%M UTC")
    total = sum(len(v) for v in categorized.values())

    nav = build_nav(categorized, topics_config)
    sections = build_topic_sections(categorized, topics_config, max_per_topic)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#1e3a5f">
  <link rel="manifest" href="manifest.json">
  <title>My News Dashboard</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    :root {{
      --bg: #0f1420;
      --surface: #1a2032;
      --surface-2: #232a3f;
      --text: #e8eaed;
      --text-dim: #9aa0ab;
      --accent: #3b82f6;
      --border: #2a3145;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding-bottom: 40px;
    }}
    header {{
      background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
      padding: 28px 20px 24px;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    }}
    header h1 {{ font-size: 22px; font-weight: 700; color: #fff; }}
    header .subtitle {{ color: #bfdbfe; font-size: 13px; margin-top: 4px; }}
    .nav {{
      display: flex; gap: 8px; overflow-x: auto; padding: 14px 20px;
      background: var(--surface); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 90;
      -webkit-overflow-scrolling: touch;
    }}
    .chip {{
      display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
      background: var(--surface-2); color: var(--text); text-decoration: none;
      padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
      border: 1px solid var(--border); transition: all 0.15s;
    }}
    .chip:hover {{ background: #2563eb; border-color: #2563eb; }}
    .chip-count {{
      background: rgba(255,255,255,0.15); border-radius: 10px;
      padding: 1px 7px; font-size: 11px;
    }}
    main {{ max-width: 780px; margin: 0 auto; padding: 20px; }}
    .topic {{ margin-bottom: 32px; scroll-margin-top: 140px; }}
    .topic-header {{
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 14px; padding-bottom: 10px;
      border-bottom: 2px solid var(--border);
    }}
    .topic-header h2 {{ font-size: 19px; font-weight: 700; }}
    .topic-count {{ color: var(--text-dim); font-size: 13px; }}
    .cards {{ display: grid; gap: 12px; }}
    .card {{
      display: block; background: var(--surface); border: 1px solid var(--border);
      border-radius: 12px; padding: 16px; text-decoration: none; color: var(--text);
      transition: all 0.15s;
    }}
    .card:hover {{ background: var(--surface-2); border-color: #3b82f6; transform: translateY(-1px); }}
    .card-title {{ font-size: 15px; font-weight: 600; line-height: 1.4; margin-bottom: 6px; }}
    .card-summary {{ font-size: 13px; color: var(--text-dim); line-height: 1.5; margin-bottom: 10px; }}
    .card-meta {{ display: flex; align-items: center; gap: 10px; font-size: 12px; }}
    .source {{
      background: var(--surface-2); color: #93c5fd; padding: 3px 9px;
      border-radius: 5px; font-weight: 600;
    }}
    .time {{ color: var(--text-dim); }}
    footer {{
      text-align: center; color: var(--text-dim); font-size: 12px;
      padding: 24px 20px; margin-top: 20px;
    }}
    .refresh-note {{ margin-top: 6px; }}
  </style>
</head>
<body>
  <header>
    <h1>My News Dashboard</h1>
    <div class="subtitle">{total} stories across {len(categorized)} topics &bull; Updated {updated_str}</div>
  </header>
  <nav class="nav">
    {nav}
  </nav>
  <main>
    {sections}
  </main>
  <footer>
    Auto-generated from RSS feeds &bull; Refreshes 3&times; daily (6AM, 12PM, 5PM PST)
    <div class="refresh-note">Pull down to refresh &bull; Last build: {updated_str}</div>
  </footer>
</body>
</html>"""
    return html


def build_manifest() -> str:
    """Build the PWA manifest.json so the site can be added to a home screen."""
    manifest = {
        "name": "My News Dashboard",
        "short_name": "News",
        "description": "Personal daily news digest across tech, finance, world, sports, and Colombia",
        "start_url": "./index.html",
        "display": "standalone",
        "background_color": "#0f1420",
        "theme_color": "#1e3a5f",
        "icons": [
            {
                "src": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4f0.png",
                "sizes": "72x72",
                "type": "image/png",
            },
            {
                "src": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4f0.png",
                "sizes": "192x192",
                "type": "image/png",
            },
        ],
    }
    return json.dumps(manifest, indent=2)


def write_site(
    categorized: dict[str, list[Article]],
    topics_config: list[dict],
    output_dir: str = "public",
    max_per_topic: int = 15,
) -> Path:
    """
    Write the complete static site to the output directory.

    Args:
        categorized: Categorized articles.
        topics_config: Raw topic config.
        output_dir: Directory to write the site into.
        max_per_topic: Max articles per topic.

    Returns:
        Path to the output directory.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    html = build_dashboard_html(categorized, topics_config, max_per_topic)
    (out / "index.html").write_text(html, encoding="utf-8")

    manifest = build_manifest()
    (out / "manifest.json").write_text(manifest, encoding="utf-8")

    # .nojekyll tells GitHub Pages to serve files as-is (skip Jekyll processing)
    (out / ".nojekyll").write_text("", encoding="utf-8")

    total = sum(len(v) for v in categorized.values())
    logger.info(
        f"Built static site at {out.resolve()} with {total} articles "
        f"across {len(categorized)} topics"
    )
    return out
