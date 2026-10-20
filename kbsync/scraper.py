"""Fetch help-center articles and convert them to Markdown."""
import logging

from .converter import Article, to_markdown
from .zendesk import fetch_articles

log = logging.getLogger(__name__)


def scrape(base_url: str, limit: int = 0) -> list[Article]:
    raw = fetch_articles(base_url, limit)
    log.info("Fetched %d articles from %s", len(raw), base_url)
    return [to_markdown(a, base_url) for a in raw]
