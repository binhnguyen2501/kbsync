from kbsync.scraper import slugify, to_markdown

BASE = "https://support.example.com"


def make(body, title="How to Add a YouTube Video!"):
    raw = {"id": 42, "title": title, "html_url": f"{BASE}/hc/en-us/articles/42", "updated_at": "2026-01-01T00:00:00Z", "body": body}
    return to_markdown(raw, BASE)


def test_slug_is_stable_and_url_safe():
    assert slugify(42, "How to Add a YouTube Video!") == "how-to-add-a-youtube-video-42"


def test_header_has_title_and_article_url():
    md = make("<p>Hi</p>").markdown
    assert md.startswith("# How to Add a YouTube Video!\n\nArticle URL: https://support.example.com/hc/en-us/articles/42\n")


def test_headings_and_code_blocks_preserved():
    md = make("<h2>Steps</h2><pre><code>adb install app.apk</code></pre>").markdown
    assert "## Steps" in md
    assert "```\nadb install app.apk\n```" in md


def test_relative_links_absolute_and_anchors_kept():
    md = make('<a href="/hc/en-us/articles/7">Other</a> <a href="#setup">Setup</a>').markdown
    assert "[Other](https://support.example.com/hc/en-us/articles/7)" in md
    assert "[Setup](#setup)" in md


def test_scripts_removed_and_iframes_become_links():
    md = make('<script>track()</script><iframe src="//www.youtube.com/embed/abc"></iframe>').markdown
    assert "track()" not in md
    assert "(https://www.youtube.com/embed/abc)" in md


def test_single_column_table_becomes_blockquote():
    md = make("<table><tr><td><strong>NOTE</strong></td></tr><tr><td>Pro only.</td></tr></table>").markdown
    assert "> **NOTE**" in md and "> Pro only." in md
    assert "|" not in md


def test_hash_changes_with_content():
    assert make("<p>a</p>").content_hash != make("<p>b</p>").content_hash
