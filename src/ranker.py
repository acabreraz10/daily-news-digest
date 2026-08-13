"""
Story Ranker
Clusters near-duplicate articles across sources, then scores each story by
importance using cross-source corroboration, source authority, feed position,
and recency. Collapses each cluster to a single representative article.

The goal: surface what matters most, not just what's newest.
"""

import logging
import math
import re
import unicodedata
from datetime import datetime, timezone

from .feeds import Article

logger = logging.getLogger(__name__)

# Common English + Spanish stopwords to ignore when comparing headlines.
_STOPWORDS = {
    # English
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those", "he", "she", "they", "we",
    "you", "his", "her", "their", "our", "will", "would", "can", "could", "has",
    "have", "had", "not", "no", "new", "says", "say", "said", "after", "over",
    "into", "up", "out", "about", "more", "than", "who", "what", "how", "why",
    # Spanish
    "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "de", "del",
    "en", "por", "para", "con", "sin", "que", "se", "su", "sus", "al", "lo",
    "es", "son", "fue", "ser", "como", "mas", "mas", "pero", "ya", "le", "les",
    "un", "una", "esta", "este", "estos", "estas", "hay", "ha", "han", "sobre",
}


def _strip_accents(text: str) -> str:
    """Remove diacritics so 'economía' and 'economia' match."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _singularize(token: str) -> str:
    """Crude singularization so 'stocks'/'stock', 'mercados'/'mercado' match."""
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def tokenize_title(title: str) -> set[str]:
    """
    Normalize a headline into a set of significant keyword tokens.

    Lowercases, strips accents/punctuation, drops stopwords and very short
    tokens, and lightly singularizes so plural/singular forms match across
    differently-worded headlines.
    """
    text = _strip_accents(title.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = {
        _singularize(t) for t in text.split()
        if len(t) > 2 and t not in _STOPWORDS
    }
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets (0-1)."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    """
    Overlap coefficient: |A n B| / min(|A|, |B|).

    Catches the case where a short headline's keywords are mostly contained in
    a longer one, even when Jaccard is low due to length difference.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def same_story(a: set[str], b: set[str], threshold: float) -> bool:
    """
    Decide whether two headlines report the same story.

    Merges when Jaccard clears the threshold, OR when the keyword overlap is
    high and at least 3 significant tokens are shared (guards against merging
    on one or two coincidental words).
    """
    if jaccard(a, b) >= threshold:
        return True
    if len(a & b) >= 3 and overlap_coefficient(a, b) >= 0.6:
        return True
    return False


class _UnionFind:
    """Simple union-find (disjoint set) for clustering."""

    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def cluster_articles(
    articles: list[Article],
    threshold: float,
) -> list[list[Article]]:
    """
    Group articles that report the same story across different sources.

    Uses keyword-token Jaccard similarity between headlines with union-find
    clustering. Articles from the same source are never merged (an outlet
    running two similar headlines is two stories, not corroboration).

    Args:
        articles: Articles to cluster.
        threshold: Minimum Jaccard similarity to consider two headlines the
            same story.

    Returns:
        List of clusters, each a list of articles.
    """
    n = len(articles)
    token_sets = [tokenize_title(a.title) for a in articles]
    uf = _UnionFind(n)

    for i in range(n):
        ti = token_sets[i]
        if not ti:
            continue
        for j in range(i + 1, n):
            # Don't merge two headlines from the same source.
            if articles[i].source == articles[j].source:
                continue
            if same_story(ti, token_sets[j], threshold):
                uf.union(i, j)

    clusters: dict[int, list[Article]] = {}
    for idx in range(n):
        root = uf.find(idx)
        clusters.setdefault(root, []).append(articles[idx])

    return list(clusters.values())


def get_authority(source: str, source_weights: dict) -> float:
    """
    Look up a source's authority weight by longest matching name prefix.

    E.g. "BBC - World" matches the "BBC" key. Falls back to the configured
    default when nothing matches.
    """
    default = source_weights.get("default", 5)
    best_key = None
    for key in source_weights:
        if key == "default":
            continue
        if source.startswith(key) or key in source:
            if best_key is None or len(key) > len(best_key):
                best_key = key
    return float(source_weights[best_key]) if best_key else float(default)


def _recency_component(published: datetime, now: datetime) -> float:
    """Exponential decay: 1.0 at publish time, ~0.37 after 12h, ~0.14 after 24h."""
    hours_old = max(0.0, (now - published).total_seconds() / 3600.0)
    return math.exp(-hours_old / 12.0)


def _position_component(best_position: int) -> float:
    """Feed position 0 -> 1.0, decays as the outlet buried the story lower."""
    return 1.0 / (1.0 + best_position / 5.0)


def score_cluster(
    cluster: list[Article],
    source_weights: dict,
    weights: dict,
    max_authority: float,
    now: datetime,
) -> tuple[Article, float, list[str]]:
    """
    Score a story cluster and pick its representative article.

    Args:
        cluster: Articles reporting the same story.
        source_weights: Source authority map.
        weights: Signal weights (corroboration, authority, position, recency).
        max_authority: Highest authority weight (for normalization).
        now: Current time (UTC).

    Returns:
        Tuple of (representative_article, score, sorted_list_of_source_names).
    """
    distinct_sources = sorted({a.source for a in cluster})

    # Corroboration: stepped so a story confirmed by multiple independent
    # outlets jumps decisively above single-source items in the ranking.
    num_sources = len(distinct_sources)
    corroboration = {1: 0.0, 2: 0.6, 3: 0.8}.get(num_sources, 1.0 if num_sources >= 4 else 0.0)

    # Authority: best source in the cluster, normalized.
    best_authority = max(get_authority(a.source, source_weights) for a in cluster)
    authority = best_authority / max_authority if max_authority else 0.0

    # Position: best (lowest) feed position across the cluster.
    best_position = min(a.feed_position for a in cluster)
    position = _position_component(best_position)

    # Recency: freshest article in the cluster.
    newest = max(cluster, key=lambda a: a.published)
    recency = _recency_component(newest.published, now)

    score = (
        weights.get("corroboration", 0.4) * corroboration
        + weights.get("authority", 0.25) * authority
        + weights.get("position", 0.15) * position
        + weights.get("recency", 0.20) * recency
    )

    # Representative: prefer highest authority, then earliest feed position,
    # then most recent. This is the "best" version of the story to link to.
    def rep_key(a: Article):
        return (
            get_authority(a.source, source_weights),
            -a.feed_position,
            a.published,
        )

    representative = max(cluster, key=rep_key)

    return representative, score, distinct_sources


def rank_stories(articles: list[Article], config: dict) -> list[Article]:
    """
    Cluster, score, and collapse articles into ranked representative stories.

    Args:
        articles: Time-filtered articles from all feeds.
        config: Full configuration dict (reads 'ranking' and 'source_weights').

    Returns:
        List of representative Article objects, each with .score and
        .corroborating_sources populated, sorted by importance (desc).
    """
    ranking = config.get("ranking", {})
    source_weights = config.get("source_weights", {"default": 5})
    weights = ranking.get("weights", {})
    threshold = ranking.get("similarity_threshold", 0.5)

    max_authority = max(
        (float(v) for k, v in source_weights.items() if k != "default"),
        default=float(source_weights.get("default", 5)),
    )

    now = datetime.now(timezone.utc)

    clusters = cluster_articles(articles, threshold)

    ranked: list[Article] = []
    for cluster in clusters:
        rep, score, sources = score_cluster(
            cluster, source_weights, weights, max_authority, now
        )
        rep.score = score
        # Corroborating sources = the *other* outlets covering this story.
        rep.corroborating_sources = [s for s in sources if s != rep.source]
        ranked.append(rep)

    ranked.sort(key=lambda a: a.score, reverse=True)

    logger.info(
        f"Ranked {len(articles)} articles into {len(ranked)} unique stories "
        f"(collapsed {len(articles) - len(ranked)} cross-source duplicates)"
    )
    return ranked
