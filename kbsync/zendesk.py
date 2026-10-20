"""Zendesk Help Center API client."""
import requests


def fetch_articles(base_url: str, limit: int = 0, locale: str = "en-us") -> list[dict]:
    """Page through /api/v2/help_center/{locale}/articles.json. limit=0 means all."""
    url = f"{base_url}/api/v2/help_center/{locale}/articles.json?per_page=100&sort_by=updated_at&sort_order=desc"
    articles: list[dict] = []
    session = requests.Session()
    while url:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        articles.extend(a for a in data["articles"] if not a.get("draft") and a.get("body"))
        if limit and len(articles) >= limit:
            return articles[:limit]
        url = data.get("next_page")
    return articles
