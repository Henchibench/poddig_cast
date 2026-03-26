import pytest
from unittest.mock import patch, MagicMock
from fetcher import fetch_articles


MOCK_CONFIG = {
    "feeds": [
        {"url": "https://example.com/feed1.xml", "topics": ["tech"]},
        {"url": "https://example.com/feed2.xml", "topics": ["ukraine"]},
    ],
    "episode": {"max_stories": 3},
}


def _make_feed(entries):
    feed = MagicMock()
    feed.bozo = False
    feed.entries = entries
    return feed


def _make_entry(title, summary, link, published):
    e = MagicMock()
    e.title = title
    e.summary = summary
    e.link = link
    e.published = published
    return e


def test_returns_top_n_articles():
    entry = _make_entry("Tech news", "Summary", "https://example.com/1", "Thu, 26 Mar 2026 07:00:00 +0000")
    with patch("fetcher.feedparser.parse", return_value=_make_feed([entry, entry, entry])):
        articles = fetch_articles(MOCK_CONFIG)
    assert len(articles) <= MOCK_CONFIG["episode"]["max_stories"]


def test_article_has_required_fields():
    entry = _make_entry("Tech news", "Summary", "https://example.com/1", "Thu, 26 Mar 2026 07:00:00 +0000")
    with patch("fetcher.feedparser.parse", return_value=_make_feed([entry])):
        articles = fetch_articles(MOCK_CONFIG)
    assert len(articles) > 0
    article = articles[0]
    assert "title" in article
    assert "summary" in article
    assert "link" in article
    assert "topics" in article


def test_failed_feed_is_skipped(caplog):
    good_entry = _make_entry("Good news", "Summary", "https://example.com/2", "Thu, 26 Mar 2026 07:00:00 +0000")
    bad_feed = MagicMock()
    bad_feed.bozo = True
    bad_feed.bozo_exception = Exception("Connection error")
    bad_feed.entries = []
    good_feed = _make_feed([good_entry])

    with patch("fetcher.feedparser.parse", side_effect=[bad_feed, good_feed]):
        articles = fetch_articles(MOCK_CONFIG)

    assert len(articles) >= 1
    assert any("Skipping feed" in r.message for r in caplog.records)


def test_all_feeds_failing_raises():
    bad_feed = MagicMock()
    bad_feed.bozo = True
    bad_feed.bozo_exception = Exception("Connection error")
    bad_feed.entries = []

    with patch("fetcher.feedparser.parse", return_value=bad_feed):
        with pytest.raises(RuntimeError, match="All RSS feeds failed"):
            fetch_articles(MOCK_CONFIG)
