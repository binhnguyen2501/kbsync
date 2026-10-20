"""Daily job: re-scrape the help center, write Markdown, upload only the delta to the vector store."""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from kbsync.config import Settings
from kbsync.scraper import scrape

OUT_DIR = Path(os.getenv("OUTPUT_DIR", "articles"))
RUN_LOG = Path(os.getenv("RUN_LOG", "logs/last_run.json"))


def main() -> int:
    settings = Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("main")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scrape-only", action="store_true", help="write Markdown files, skip the upload")
    args = parser.parse_args()

    started = time.monotonic()
    articles = scrape(settings.zendesk_base_url, limit=settings.max_articles)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for a in articles:
        (OUT_DIR / f"{a.slug}.md").write_text(a.markdown, encoding="utf-8")
    log.info("Wrote %d Markdown files to %s/", len(articles), OUT_DIR)
    if args.scrape_only:
        return 0

    if not settings.api_key:
        log.error("Set OPENAI_API_KEY (or API_KEY)")
        return 2

    from openai import OpenAI
    from kbsync.uploader import get_or_create_vector_store, sync

    client = OpenAI(api_key=settings.api_key)
    store_id = get_or_create_vector_store(client, settings.vector_store_id, settings.vector_store_name)
    result = sync(client, store_id, articles)

    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vector_store_id": store_id,
        "scraped": len(articles),
        "added": len(result.added),
        "updated": len(result.updated),
        "skipped": len(result.skipped),
        "failed": len(result.failed),
        "files_embedded": len(result.added) + len(result.updated),
        "chunks_embedded_est": result.chunks,
        "duration_s": round(time.monotonic() - started, 1),
        "changed": {"added": result.added, "updated": result.updated, "failed": result.failed},
    }
    log.info(
        "added=%d updated=%d skipped=%d failed=%d | embedded files=%d chunks~%d",
        summary["added"], summary["updated"], summary["skipped"], summary["failed"],
        summary["files_embedded"], summary["chunks_embedded_est"],
    )
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
