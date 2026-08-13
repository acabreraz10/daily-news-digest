"""
Static Site Builder
Generates a responsive HTML dashboard (+ PWA manifest) for the news digest.
Designed to be published on GitHub Pages.

Layout:
- A cross-topic "Top Stories" hero with the highest-importance stories.
- Per-topic sections showing a tight preview, with the rest tucked behind a
  native "show more" expander.
"""

import json
import logging
from datetime import datetime, timezone
from html import escape
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


def _anchor(topic_name: str) -> str:
    """Turn a topic name into a URL anchor."""
    return topic_name.lower().replace(" ", "-").replace("&", "and")


def _sources_badge(article: Article) -> str:
    """Build a '+N sources' corroboration badge if the story is multi-sourced."""
    n = len(article.corroborating_sources)
    if n <= 0:
        return ""
    label = f"+{n} source" + ("s" if n != 1 else "")
    title = "Also covered by: " + escape(", ".join(article.corroborating_sources))
    return f'<span class="badge-sources" title="{title}">{label}</span>'


def build_nav(categorized: dict[str, list[Article]], topics_config: list[dict]) -> str:
    """Build the topic navigation chips (with a Top Stories chip first)."""
    chips = '<a href="#top-stories" class="chip chip-top">\u2b50 Top Stories</a>'
    for topic_name in categorized:
        icon = get_topic_icon(topic_name, topics_config)
        chips += (
            f'<a href="#{_anchor(topic_name)}" class="chip">{icon} {escape(topic_name)}'
            f'<span class="chip-count">{len(categorized[topic_name])}</span></a>'
        )
    return chips


def build_hero(top_stories: list[Article], topics_config: list[dict]) -> str:
    """Build the cross-topic Top Stories hero section."""
    if not top_stories:
        return ""

    items = ""
    for rank, a in enumerate(top_stories, start=1):
        icon = get_topic_icon(a.topic, topics_config) if a.topic else ""
        topic_tag = (
            f'<span class="hero-topic">{icon} {escape(a.topic)}</span>' if a.topic else ""
        )
        items += f"""
        <a class="hero-card" href="{escape(a.link)}" target="_blank" rel="noopener noreferrer">
          <span class="hero-rank">{rank}</span>
          <div class="hero-body">
            <div class="hero-title">{escape(a.title)}</div>
            <div class="hero-meta">
              {topic_tag}
              <span class="source">{escape(a.source)}</span>
              {_sources_badge(a)}
              <span class="time">{format_time_ago(a.published)}</span>
            </div>
          </div>
        </a>"""

    return f"""
      <section id="top-stories" class="hero">
        <div class="hero-header">
          <h2>\u2b50 Top Stories</h2>
          <span class="hero-sub">What to know right now</span>
        </div>
        <div class="hero-cards">
          {items}
        </div>
      </section>"""


def _article_card(a: Article) -> str:
    """Build a single article card."""
    summary = escape(a.summary) if a.summary else ""
    return f"""
          <a class="card" href="{escape(a.link)}" target="_blank" rel="noopener noreferrer">
            <div class="card-title">{escape(a.title)}</div>
            <div class="card-summary">{summary}</div>
            <div class="card-meta">
              <span class="source">{escape(a.source)}</span>
              {_sources_badge(a)}
              <span class="time">{format_time_ago(a.published)}</span>
            </div>
          </a>"""


def build_topic_sections(
    categorized: dict[str, list[Article]],
    topics_config: list[dict],
    max_per_topic: int,
    preview_per_topic: int,
) -> str:
    """
    Build the per-topic sections.

    Shows the top `preview_per_topic` stories by importance, then tucks the
    remainder (up to `max_per_topic`) behind a native <details> expander.
    """
    sections = ""
    for topic_name, articles in categorized.items():
        icon = get_topic_icon(topic_name, topics_config)
        anchor = _anchor(topic_name)
        capped = articles[:max_per_topic]
        preview = capped[:preview_per_topic]
        remainder = capped[preview_per_topic:]

        preview_cards = "".join(_article_card(a) for a in preview)

        more_block = ""
        if remainder:
            more_cards = "".join(_article_card(a) for a in remainder)
            more_block = f"""
          <details class="more">
            <summary>Show {len(remainder)} more</summary>
            <div class="cards">
              {more_cards}
            </div>
          </details>"""

        sections += f"""
      <section id="{anchor}" class="topic">
        <div class="topic-header">
          <h2>{icon} {escape(topic_name)}</h2>
          <span class="topic-count">{len(capped)} stories</span>
        </div>
        <div class="cards">
          {preview_cards}
        </div>
        {more_block}
      </section>"""
    return sections


def build_dashboard_html(
    categorized: dict[str, list[Article]],
    topics_config: list[dict],
    top_stories: list[Article],
    max_per_topic: int = 25,
    preview_per_topic: int = 5,
) -> str:
    """Build the complete HTML dashboard page."""
    now = datetime.now(timezone.utc)
    updated_str = now.strftime("%b %d, %Y at %H:%M UTC")
    total = sum(len(v) for v in categorized.values())

    nav = build_nav(categorized, topics_config)
    hero = build_hero(top_stories, topics_config)
    sections = build_topic_sections(
        categorized, topics_config, max_per_topic, preview_per_topic
    )

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
      --gold: #f5c518;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding-bottom: 40px;
    }}
    header {{
      background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
      padding: 28px 20px 24px;
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
    .chip-top {{ background: rgba(245,197,24,0.12); border-color: var(--gold); color: var(--gold); }}
    .chip-count {{
      background: rgba(255,255,255,0.15); border-radius: 10px;
      padding: 1px 7px; font-size: 11px;
    }}
    main {{ max-width: 780px; margin: 0 auto; padding: 20px; }}

    /* Hero / Top Stories */
    .hero {{ margin-bottom: 36px; scroll-margin-top: 80px; }}
    .hero-header {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }}
    .hero-header h2 {{ font-size: 22px; font-weight: 800; }}
    .hero-sub {{ color: var(--text-dim); font-size: 13px; }}
    .hero-cards {{ display: grid; gap: 10px; }}
    .hero-card {{
      display: flex; gap: 14px; align-items: flex-start;
      background: linear-gradient(135deg, #1c2438 0%, #1a2032 100%);
      border: 1px solid var(--border); border-left: 3px solid var(--gold);
      border-radius: 12px; padding: 14px 16px; text-decoration: none; color: var(--text);
      transition: all 0.15s;
    }}
    .hero-card:hover {{ background: var(--surface-2); transform: translateY(-1px); }}
    .hero-rank {{
      font-size: 20px; font-weight: 800; color: var(--gold);
      min-width: 24px; text-align: center; opacity: 0.85;
    }}
    .hero-title {{ font-size: 16px; font-weight: 700; line-height: 1.35; margin-bottom: 6px; }}
    .hero-meta, .card-meta {{ display: flex; align-items: center; gap: 8px; font-size: 12px; flex-wrap: wrap; }}
    .hero-topic {{ color: #93c5fd; font-weight: 600; }}

    /* Topic sections */
    .topic {{ margin-bottom: 32px; scroll-margin-top: 80px; }}
    .topic-header {{
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 14px; padding-bottom: 10px; border-bottom: 2px solid var(--border);
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
    .source {{ background: var(--surface-2); color: #93c5fd; padding: 3px 9px; border-radius: 5px; font-weight: 600; }}
    .badge-sources {{ background: rgba(245,197,24,0.15); color: var(--gold); padding: 3px 9px; border-radius: 5px; font-weight: 600; }}
    .time {{ color: var(--text-dim); }}

    /* Show more expander */
    .more {{ margin-top: 12px; }}
    .more > summary {{
      cursor: pointer; list-style: none; text-align: center;
      background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
      padding: 10px; font-size: 13px; font-weight: 600; color: #93c5fd;
      transition: all 0.15s;
    }}
    .more > summary:hover {{ background: var(--surface-2); }}
    .more[open] > summary {{ margin-bottom: 12px; }}
    .more > summary::-webkit-details-marker {{ display: none; }}

    footer {{ text-align: center; color: var(--text-dim); font-size: 12px; padding: 24px 20px; margin-top: 20px; }}
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
    {hero}
    {sections}
  </main>
  <footer>
    Auto-generated from RSS feeds &bull; Ranked by cross-source importance &bull; Refreshes 3&times; daily
    <div class="refresh-note">Last build: {updated_str}</div>
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
    max_per_topic: int = 25,
    top_stories: list[Article] | None = None,
    preview_per_topic: int = 5,
) -> Path:
    """
    Write the complete static site to the output directory.

    Args:
        categorized: Categorized articles (each bucket pre-sorted by score).
        topics_config: Raw topic config.
        output_dir: Directory to write the site into.
        max_per_topic: Max articles per topic (preview + expander combined).
        top_stories: Highest-importance stories for the hero section.
        preview_per_topic: Stories shown per topic before the "show more".

    Returns:
        Path to the output directory.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    html = build_dashboard_html(
        categorized,
        topics_config,
        top_stories=top_stories or [],
        max_per_topic=max_per_topic,
        preview_per_topic=preview_per_topic,
    )
    (out / "index.html").write_text(html, encoding="utf-8")

    manifest = build_manifest()
    (out / "manifest.json").write_text(manifest, encoding="utf-8")

    # .nojekyll tells GitHub Pages to serve files as-is (skip Jekyll processing)
    (out / ".nojekyll").write_text("", encoding="utf-8")

    total = sum(len(v) for v in categorized.values())
    logger.info(
        f"Built static site at {out.resolve()} with {total} stories "
        f"across {len(categorized)} topics ({len(top_stories or [])} in Top Stories)"
    )
    return out
