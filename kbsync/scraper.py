"""Fetch help-center articles via the Zendesk Help Center API and convert them to Markdown."""
import hashlib
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

log = logging.getLogger(__name__)

# Tags that never carry article content (embeds, scripts, tracking, forms).
STRIP_TAGS = ["script", "style", "noscript", "form", "button", "nav", "footer", "header", "aside"]


@dataclass
class Article:
    id: int
    slug: str
    title: str
    url: str
    updated_at: str
    markdown: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.markdown.encode("utf-8")).hexdigest()


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


def slugify(article_id: int, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80].rstrip("-")
    return f"{slug}-{article_id}"


def _clean_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()
    # Video embeds have no Markdown equivalent: keep them as a plain link.
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            iframe.replace_with(soup.new_tag("a", href=src, string=f"Embedded video: {src}"))
        else:
            iframe.decompose()
    # Zendesk uses one-column tables as callout boxes ("NOTE", "TIP"); render them as blockquotes.
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if rows and all(len(r.find_all(["td", "th"])) == 1 for r in rows):
            quote = soup.new_tag("blockquote")
            for r in rows:
                cell = r.find(["td", "th"])
                p = soup.new_tag("p")
                p.extend(list(cell.contents))
                quote.append(p)
            table.replace_with(quote)
    # Site-relative links ("/hc/en-us/articles/...") would break once the file leaves the site;
    # in-page anchors ("#section") are kept as-is.
    for tag, attr in (("a", "href"), ("img", "src")):
        for el in soup.find_all(tag):
            val = el.get(attr)
            if val and val.startswith("/") and not val.startswith("//"):
                el[attr] = urljoin(base_url, val)
    return str(soup)


class _Converter(MarkdownConverter):
    # Zendesk wraps code in <pre><code>; keep the fence language-agnostic.
    def convert_pre(self, el, text, *args, **kwargs):
        code = el.get_text()
        return f"\n\n```\n{code.strip()}\n```\n\n"


def to_markdown(raw: dict, base_url: str) -> Article:
    body = _clean_html(raw["body"], base_url)
    md = _Converter(heading_style="ATX", bullets="-", strip=["span"]).convert(body)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    header = f"# {raw['title']}\n\nArticle URL: {raw['html_url']}\n\n"
    return Article(
        id=raw["id"],
        slug=slugify(raw["id"], raw["title"]),
        title=raw["title"],
        url=raw["html_url"],
        updated_at=raw["updated_at"],
        markdown=header + md + "\n",
    )


def scrape(base_url: str, limit: int = 0) -> list[Article]:
    raw = fetch_articles(base_url, limit)
    log.info("Fetched %d articles from %s", len(raw), base_url)
    return [to_markdown(a, base_url) for a in raw]
