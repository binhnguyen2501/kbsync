"""Sync Markdown articles into an OpenAI vector store, uploading only what changed.

State lives on the vector store itself: every file carries `attributes`
({article_id, content_hash, ...}), so the job needs no local disk between runs.
"""
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from openai import OpenAI

from .converter import Article

log = logging.getLogger(__name__)

# Static chunking: help articles are short, task-focused docs. ~800 tokens fits one
# procedure/section; 400 overlap keeps steps that straddle a boundary intact.
MAX_CHUNK_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 400
CHUNKING_STRATEGY = {
    "type": "static",
    "static": {"max_chunk_size_tokens": MAX_CHUNK_TOKENS, "chunk_overlap_tokens": CHUNK_OVERLAP_TOKENS},
}


def estimate_chunks(text: str) -> int:
    """The API does not report chunk counts; estimate them from the static strategy (~4 chars/token)."""
    tokens = max(1, len(text) // 4)
    if tokens <= MAX_CHUNK_TOKENS:
        return 1
    step = MAX_CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
    return 1 + math.ceil((tokens - MAX_CHUNK_TOKENS) / step)


@dataclass
class SyncResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    chunks: int = 0


def get_or_create_vector_store(client: OpenAI, store_id: str | None, name: str) -> str:
    if store_id:
        return client.vector_stores.retrieve(store_id).id
    for vs in client.vector_stores.list(limit=100):
        if vs.name == name:
            return vs.id
    vs = client.vector_stores.create(name=name)
    log.info("Created vector store %s (%s)", name, vs.id)
    return vs.id


def _existing_files(client: OpenAI, store_id: str) -> dict[str, tuple[str, str]]:
    """article_id -> (file_id, content_hash) for files already in the store."""
    existing = {}
    for f in client.vector_stores.files.list(vector_store_id=store_id, limit=100):
        attrs = f.attributes or {}
        if "article_id" in attrs:
            existing[str(attrs["article_id"])] = (f.id, str(attrs.get("content_hash", "")))
    return existing


def _upload(client: OpenAI, store_id: str, article: Article) -> None:
    uploaded = client.files.create(file=(f"{article.slug}.md", article.markdown.encode("utf-8")), purpose="assistants")
    vs_file = client.vector_stores.files.create_and_poll(
        vector_store_id=store_id,
        file_id=uploaded.id,
        chunking_strategy=CHUNKING_STRATEGY,
        attributes={
            "article_id": str(article.id),
            "content_hash": article.content_hash,
            "slug": article.slug[:500],
            "url": article.url[:500],
            "updated_at": article.updated_at,
        },
    )
    if vs_file.status != "completed":
        raise RuntimeError(f"embedding {vs_file.status}: {vs_file.last_error}")


def _remove(client: OpenAI, store_id: str, file_id: str) -> None:
    client.vector_stores.files.delete(file_id=file_id, vector_store_id=store_id)
    client.files.delete(file_id)


def sync(client: OpenAI, store_id: str, articles: list[Article], workers: int = 8) -> SyncResult:
    existing = _existing_files(client, store_id)
    log.info("Vector store %s currently holds %d article files", store_id, len(existing))
    result = SyncResult()

    def handle(article: Article) -> None:
        key = str(article.id)
        prev = existing.get(key)
        if prev and prev[1] == article.content_hash:
            result.skipped.append(article.slug)
            return
        try:
            _upload(client, store_id, article)
            if prev:
                _remove(client, store_id, prev[0])  # drop the stale version only after the new one is live
                result.updated.append(article.slug)
            else:
                result.added.append(article.slug)
        except Exception as exc:  # one bad article should not sink the whole run
            log.error("Failed to upload %s: %s", article.slug, exc)
            result.failed.append(article.slug)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(handle, articles))
    changed = set(result.added) | set(result.updated)
    result.chunks = sum(estimate_chunks(a.markdown) for a in articles if a.slug in changed)
    return result
