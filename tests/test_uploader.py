from types import SimpleNamespace

from kbsync import uploader
from kbsync.converter import Article
from kbsync.uploader import estimate_chunks, sync


def art(i, text):
    return Article(id=i, slug=f"a-{i}", title="t", url=f"u/{i}", updated_at="", markdown=text)


class FakeFiles:
    def __init__(self, existing):
        self.existing = existing  # list of (file_id, attributes)

    def list(self, vector_store_id, limit):
        return [SimpleNamespace(id=fid, attributes=attrs) for fid, attrs in self.existing]


def test_sync_classifies_added_updated_skipped(monkeypatch):
    same, changed, new = art(1, "same"), art(2, "new text"), art(3, "brand new")
    client = SimpleNamespace(vector_stores=SimpleNamespace(files=FakeFiles([
        ("f1", {"article_id": "1", "content_hash": same.content_hash}),
        ("f2", {"article_id": "2", "content_hash": "stale"}),
    ])))
    uploads, removals = [], []
    monkeypatch.setattr(uploader, "_upload", lambda c, s, a: uploads.append(a.slug))
    monkeypatch.setattr(uploader, "_remove", lambda c, s, fid: removals.append(fid))

    result = sync(client, "vs_1", [same, changed, new], workers=1)

    assert result.skipped == ["a-1"]
    assert result.updated == ["a-2"]
    assert result.added == ["a-3"]
    assert sorted(uploads) == ["a-2", "a-3"]
    assert removals == ["f2"]  # stale version dropped only for the updated article


def test_failed_upload_is_reported_not_raised(monkeypatch):
    client = SimpleNamespace(vector_stores=SimpleNamespace(files=FakeFiles([])))

    def boom(c, s, a):
        raise RuntimeError("network")

    monkeypatch.setattr(uploader, "_upload", boom)
    result = sync(client, "vs_1", [art(1, "x")], workers=1)
    assert result.failed == ["a-1"] and not result.added


def test_estimate_chunks():
    assert estimate_chunks("x" * 100) == 1
    assert estimate_chunks("x" * 4 * 800) == 1
    assert estimate_chunks("x" * 4 * 1600) == 3  # 800 + 2 steps of 400
