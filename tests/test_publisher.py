import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from publisher import publish_episode, update_feed_xml


MOCK_CONFIG = {
    "github": {
        "owner": "testuser",
        "repo": "poddig_cast",
        "pages_branch": "main",
    },
}

MOCK_SCRIPT = {"title": "Poddig Cast - 26 mars 2026"}

INITIAL_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Poddig Cast</title>
    <link>https://testuser.github.io/poddig_cast/</link>
    <description>Din automatiska svenska nyhetspodcast</description>
    <language>sv</language>
  </channel>
</rss>"""


def test_update_feed_xml_adds_item(tmp_path):
    feed_path = tmp_path / "feed.xml"
    feed_path.write_text(INITIAL_FEED, encoding="utf-8")

    update_feed_xml(
        feed_path=feed_path,
        title="Poddig Cast - 26 mars 2026",
        mp3_url="https://github.com/testuser/poddig_cast/releases/download/ep-2026-03-26/episode.mp3",
        mp3_size=1234567,
        date_str="Thu, 26 Mar 2026 07:00:00 +0000",
    )

    content = feed_path.read_text(encoding="utf-8")
    assert "<item>" in content
    assert "Poddig Cast - 26 mars 2026" in content
    assert "ep-2026-03-26" in content
    assert "enclosure" in content


def test_update_feed_xml_prepends_newest_first(tmp_path):
    feed_path = tmp_path / "feed.xml"
    feed_path.write_text(INITIAL_FEED, encoding="utf-8")

    update_feed_xml(feed_path, "Episode 1", "https://example.com/1.mp3", 100, "Thu, 26 Mar 2026 07:00:00 +0000")
    update_feed_xml(feed_path, "Episode 2", "https://example.com/2.mp3", 200, "Sat, 28 Mar 2026 07:00:00 +0000")

    content = feed_path.read_text(encoding="utf-8")
    assert content.index("Episode 2") < content.index("Episode 1")


def test_publish_episode_creates_release(tmp_path):
    mp3_path = tmp_path / "episode.mp3"
    mp3_path.write_bytes(b"fake_mp3")

    mock_release_response = MagicMock()
    mock_release_response.status_code = 201
    mock_release_response.json.return_value = {
        "upload_url": "https://uploads.github.com/repos/testuser/poddig_cast/releases/1/assets{?name,label}",
        "html_url": "https://github.com/testuser/poddig_cast/releases/tag/ep-2026-03-26",
    }

    mock_asset_response = MagicMock()
    mock_asset_response.status_code = 201
    mock_asset_response.json.return_value = {
        "browser_download_url": "https://github.com/testuser/poddig_cast/releases/download/ep-2026-03-26/episode.mp3"
    }

    feed_path = tmp_path / "feed.xml"
    feed_path.write_text(INITIAL_FEED, encoding="utf-8")

    with patch("publisher.requests.post", side_effect=[mock_release_response, mock_asset_response]) as mock_post, \
         patch("publisher.subprocess.run") as mock_sub, \
         patch("publisher.FEED_PATH", feed_path), \
         patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
        mp3_url = publish_episode(mp3_path, MOCK_SCRIPT, MOCK_CONFIG)

    assert "ep-2026-03-26" in mp3_url
    mock_sub.assert_any_call(["git", "push"], check=True)
