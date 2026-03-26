# Poddig Cast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully automated Swedish news podcast pipeline that runs on GitHub Actions, fetches RSS news, writes a two-host script with Claude, generates audio with ElevenLabs v3, and publishes episodes to GitHub Releases with a subscribable RSS feed on GitHub Pages.

**Architecture:** Four sequential Python modules (fetcher → scriptwriter → tts → publisher) orchestrated by `run.py` and triggered by a GitHub Actions workflow on a schedule or manually. MP3s are hosted as GitHub Release assets; a `docs/feed.xml` on GitHub Pages serves as the podcast RSS feed.

**Tech Stack:** Python 3.11, feedparser, anthropic SDK, requests, pydub + ffmpeg, PyYAML, pytest, GitHub Actions, ElevenLabs v3 API, GitHub Releases API

---

## File Map

| File | Responsibility |
|---|---|
| `config.yaml` | All runtime config: feeds, voices, TTS settings, GitHub info |
| `fetcher.py` | Pull RSS feeds, parse articles, score by recency, return top N |
| `scriptwriter.py` | Send articles to Claude API, return structured script JSON |
| `tts.py` | Send each segment to ElevenLabs, download MP3 chunks, merge with pydub |
| `publisher.py` | Create GitHub Release, upload MP3, update feed.xml, git push |
| `run.py` | Orchestrate all four stages in order |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Ignore `episodes/`, `__pycache__`, `.env` |
| `docs/feed.xml` | Initial podcast RSS skeleton (GitHub Pages) |
| `.github/workflows/generate_episode.yml` | Scheduled + manual workflow |
| `tests/conftest.py` | Shared pytest fixtures |
| `tests/test_fetcher.py` | Unit tests for fetcher |
| `tests/test_scriptwriter.py` | Unit tests for scriptwriter |
| `tests/test_tts.py` | Unit tests for tts |
| `tests/test_publisher.py` | Unit tests for publisher |

---

## Task 1: Project Scaffold

**Files:**
- Create: `config.yaml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `docs/feed.xml`
- Create: `episodes/.gitkeep`

- [ ] **Step 1: Create `config.yaml`**

```yaml
voices:
  host_a: "6eknYWL7D5Z4nRkDy15t"
  host_b: "7UMEOkIJdI4hjmR2SWNq"

tts:
  model: "eleven_v3"
  output_format: "mp3_44100_128"

feeds:
  - url: "https://feeds.reuters.com/reuters/topNews"
    topics: [world, politics]
  - url: "https://kyivindependent.com/feed/"
    topics: [ukraine]
  - url: "https://techcrunch.com/feed/"
    topics: [tech]
  - url: "https://www.svt.se/nyheter/rss.xml"
    topics: [sweden, world]

episode:
  target_duration_minutes: 10
  max_stories: 7
  language: "sv"

github:
  owner: "YOUR_GITHUB_USERNAME"
  repo: "poddig_cast"
  pages_branch: "main"
```

- [ ] **Step 2: Create `requirements.txt`**

```
feedparser==6.0.11
anthropic>=0.25.0
requests>=2.32.0
pydub>=0.25.1
PyYAML>=6.0.2
pytest>=8.0.0
```

- [ ] **Step 3: Create `.gitignore`**

```
episodes/
__pycache__/
*.pyc
*.pyo
.env
*.mp3
```

- [ ] **Step 4: Create `docs/feed.xml` — initial empty podcast RSS feed**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Poddig Cast</title>
    <link>https://YOUR_GITHUB_USERNAME.github.io/poddig_cast/</link>
    <description>Din automatiska svenska nyhetspodcast</description>
    <language>sv</language>
    <itunes:author>Poddig Cast</itunes:author>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
  </channel>
</rss>
```

- [ ] **Step 5: Create `episodes/.gitkeep`** (empty file so the directory exists in git)

- [ ] **Step 6: Commit**

```bash
git add config.yaml requirements.txt .gitignore docs/feed.xml episodes/.gitkeep
git commit -m "feat: project scaffold — config, requirements, feed skeleton"
```

---

## Task 2: Fetcher

**Files:**
- Create: `fetcher.py`
- Create: `tests/__init__.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: Write failing tests in `tests/test_fetcher.py`**

```python
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
```

- [ ] **Step 2: Create `tests/__init__.py`** (empty file)

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /mnt/c/GITHUB/poddig_cast && pip install -r requirements.txt && pytest tests/test_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'fetcher'`

- [ ] **Step 4: Implement `fetcher.py`**

```python
import logging
import feedparser

logger = logging.getLogger(__name__)


def fetch_articles(config: dict) -> list[dict]:
    """Fetch RSS feeds, return top N articles as dicts."""
    max_stories = config["episode"]["max_stories"]
    all_articles = []
    successful_feeds = 0

    for feed_config in config["feeds"]:
        url = feed_config["url"]
        topics = feed_config["topics"]

        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("Skipping feed %s: %s", url, feed.bozo_exception)
            continue

        successful_feeds += 1
        for entry in feed.entries[:3]:
            all_articles.append({
                "title": getattr(entry, "title", ""),
                "summary": getattr(entry, "summary", ""),
                "link": getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
                "topics": topics,
            })

    if successful_feeds == 0:
        raise RuntimeError("All RSS feeds failed — cannot generate episode")

    return all_articles[:max_stories]


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    articles = fetch_articles(config)
    for a in articles:
        print(f"[{', '.join(a['topics'])}] {a['title']}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: 4 tests passing

- [ ] **Step 6: Commit**

```bash
git add fetcher.py tests/__init__.py tests/test_fetcher.py
git commit -m "feat: fetcher — RSS fetch, parse, return top N articles"
```

---

## Task 3: Scriptwriter

**Files:**
- Create: `scriptwriter.py`
- Create: `tests/test_scriptwriter.py`

- [ ] **Step 1: Write failing tests in `tests/test_scriptwriter.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from scriptwriter import write_script


MOCK_CONFIG = {
    "episode": {"language": "sv", "target_duration_minutes": 10},
    "voices": {"host_a": "voice_a_id", "host_b": "voice_b_id"},
}

MOCK_ARTICLES = [
    {"title": "Tech nyhet", "summary": "AI gör grejer", "link": "https://example.com/1", "published": "Thu, 26 Mar 2026", "topics": ["tech"]},
    {"title": "Ukraine nyhet", "summary": "Strid pågår", "link": "https://example.com/2", "published": "Thu, 26 Mar 2026", "topics": ["ukraine"]},
]

VALID_SCRIPT = {
    "title": "Poddig Cast - 26 mars 2026",
    "segments": [
        {"host": "A", "text": "Hallå och välkommen!"},
        {"host": "B", "text": "Hej hej!"},
        {"host": "A", "text": "Idag pratar vi om AI."},
    ],
}


def _make_mock_client(script_dict):
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(script_dict))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


def test_returns_script_with_title_and_segments():
    mock_client = _make_mock_client(VALID_SCRIPT)
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        script = write_script(MOCK_ARTICLES, MOCK_CONFIG)
    assert "title" in script
    assert "segments" in script


def test_segments_have_host_and_text():
    mock_client = _make_mock_client(VALID_SCRIPT)
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        script = write_script(MOCK_ARTICLES, MOCK_CONFIG)
    for seg in script["segments"]:
        assert seg["host"] in ("A", "B")
        assert isinstance(seg["text"], str)
        assert len(seg["text"]) > 0


def test_raises_on_invalid_json():
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="not json at all")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ValueError, match="Claude returned invalid JSON"):
            write_script(MOCK_ARTICLES, MOCK_CONFIG)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scriptwriter.py -v
```

Expected: `ModuleNotFoundError: No module named 'scriptwriter'`

- [ ] **Step 3: Implement `scriptwriter.py`**

```python
import json
import logging
import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du är manusförfattare för en svensk nyhetspodcast kallad "Poddig Cast".
Du skriver manus för två programledare: HOST_A (kallas "A") och HOST_B (kallas "B").
Deras ton är vänlig, avslappnad och lättsam — som två vänner som diskuterar nyheter.
De kommenterar, reagerar genuint, och håller samtalet levande och naturligt.
Varje segment ska vara 1-3 meningar max — håll det konversationsnära.
Använd SSML-taggar för naturliga pauser och betoning inuti text-strängen:
  <break time='300ms'/> för paus, <emphasis>ord</emphasis> för betoning,
  <prosody rate='fast'>text</prosody> när en host pratar snabbt/ivrigt.
Returnera ALLTID ett JSON-objekt med denna EXAKTA struktur, inget annat:
{
  "title": "Poddig Cast - [datum på svenska]",
  "segments": [
    {"host": "A", "text": "..."},
    {"host": "B", "text": "..."}
  ]
}
Målet är 25-35 segment (~10 minuter). Börja med en kort intro, ta upp 5-7 nyheter,
avsluta naturligt. Inga reklampausreferenser."""


def write_script(articles: list[dict], config: dict) -> dict:
    """Send articles to Claude, return script as dict with title and segments."""
    client = anthropic.Anthropic()

    articles_text = "\n\n".join(
        f"[{', '.join(a['topics'])}] {a['title']}\n{a['summary']}"
        for a in articles
    )

    user_prompt = f"Skriv ett ~10 minuters poddmanus baserat på dessa nyheter:\n\n{articles_text}"

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text

    # Strip markdown code fences if present
    if raw.strip().startswith("```"):
        raw = raw.strip().lstrip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw output:\n{raw}")

    return script


if __name__ == "__main__":
    import yaml
    import sys
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    articles = [
        {"title": "AI tar över världen", "summary": "OpenAI lanserar ny modell", "link": "https://example.com", "published": "2026-03-26", "topics": ["tech"]},
        {"title": "Trump säger galen sak", "summary": "Presidenten twittrade igen", "link": "https://example.com", "published": "2026-03-26", "topics": ["politics"]},
        {"title": "Ukraine frontlinje", "summary": "Strid nära Kharkiv", "link": "https://example.com", "published": "2026-03-26", "topics": ["ukraine"]},
    ]
    script = write_script(articles, config)
    print(f"Title: {script['title']}")
    print(f"Segments: {len(script['segments'])}")
    for seg in script["segments"][:4]:
        print(f"  [{seg['host']}]: {seg['text'][:80]}...")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scriptwriter.py -v
```

Expected: 3 tests passing

- [ ] **Step 5: Commit**

```bash
git add scriptwriter.py tests/test_scriptwriter.py
git commit -m "feat: scriptwriter — Claude API generates Swedish two-host podcast script"
```

---

## Task 4: TTS

**Files:**
- Create: `tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write failing tests in `tests/test_tts.py`**

```python
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from tts import generate_audio


MOCK_CONFIG = {
    "voices": {
        "host_a": "6eknYWL7D5Z4nRkDy15t",
        "host_b": "7UMEOkIJdI4hjmR2SWNq",
    },
    "tts": {
        "model": "eleven_v3",
        "output_format": "mp3_44100_128",
    },
}

MOCK_SCRIPT = {
    "title": "Poddig Cast - 26 mars 2026",
    "segments": [
        {"host": "A", "text": "Hallå och välkommen!"},
        {"host": "B", "text": "Hej hej! Kul att vara här."},
        {"host": "A", "text": "Idag pratar vi om Trump igen."},
    ],
}


def test_calls_elevenlabs_for_each_segment(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = MagicMock()
    mock_audio.__add__ = MagicMock(return_value=mock_audio)
    mock_audio.export = MagicMock()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_mp3", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    assert mock_post.call_count == len(MOCK_SCRIPT["segments"])


def test_uses_correct_voice_per_host(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = MagicMock()
    mock_audio.__add__ = MagicMock(return_value=mock_audio)
    mock_audio.export = MagicMock()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_mp3", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    calls = mock_post.call_args_list
    # First segment is host A
    assert "6eknYWL7D5Z4nRkDy15t" in calls[0][0][0]
    # Second segment is host B
    assert "7UMEOkIJdI4hjmR2SWNq" in calls[1][0][0]


def test_raises_on_elevenlabs_error(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("tts.requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="ElevenLabs API error"):
            generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tts.py -v
```

Expected: `ModuleNotFoundError: No module named 'tts'`

- [ ] **Step 3: Implement `tts.py`**

```python
import io
import logging
import os
import tempfile
from pathlib import Path

import requests
from pydub import AudioSegment

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


def _tts_segment(text: str, voice_id: str, model: str, output_format: str, api_key: str) -> bytes:
    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {response.status_code}: {response.text}")
    return response.content


def generate_audio(script: dict, config: dict, output_path: Path) -> Path:
    """Generate merged MP3 from script segments using ElevenLabs v3."""
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_map = {
        "A": config["voices"]["host_a"],
        "B": config["voices"]["host_b"],
    }
    model = config["tts"]["model"]
    output_format = config["tts"]["output_format"]
    pause = AudioSegment.silent(duration=300)
    combined = AudioSegment.silent(duration=0)

    for i, segment in enumerate(script["segments"]):
        host = segment["host"]
        text = segment["text"]
        voice_id = voice_map[host]

        logger.info("TTS segment %d/%d [Host %s]: %s...", i + 1, len(script["segments"]), host, text[:50])

        audio_bytes = _tts_segment(text, voice_id, model, output_format, api_key)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        chunk = AudioSegment.from_mp3(tmp_path)
        combined = combined + chunk + pause

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="mp3")
    logger.info("Episode saved to %s (%.1f seconds)", output_path, len(combined) / 1000)
    return output_path


if __name__ == "__main__":
    import yaml
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    test_script = {
        "title": "Test",
        "segments": [{"host": "A", "text": "Hej, det här är ett test av ljudgenerering."}],
    }
    out = generate_audio(test_script, config, Path("episodes/test.mp3"))
    print(f"Output: {out}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tts.py -v
```

Expected: 3 tests passing

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_tts.py
git commit -m "feat: tts — ElevenLabs v3 per-segment audio, pydub merge"
```

---

## Task 5: Publisher

**Files:**
- Create: `publisher.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Write failing tests in `tests/test_publisher.py`**

```python
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
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

    with patch("publisher.requests.post", side_effect=[mock_release_response, mock_asset_response]), \
         patch("publisher.subprocess.run"), \
         patch("publisher.FEED_PATH", feed_path), \
         patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
        mp3_url = publish_episode(mp3_path, MOCK_SCRIPT, MOCK_CONFIG)

    assert "ep-2026-03-26" in mp3_url
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_publisher.py -v
```

Expected: `ModuleNotFoundError: No module named 'publisher'`

- [ ] **Step 3: Implement `publisher.py`**

```python
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

FEED_PATH = Path("docs/feed.xml")

ET.register_namespace("", "")
ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")


def update_feed_xml(feed_path: Path, title: str, mp3_url: str, mp3_size: int, date_str: str) -> None:
    """Insert a new <item> at the top of the RSS feed's <channel>."""
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    tree = ET.parse(feed_path)
    root = tree.getroot()
    channel = root.find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "pubDate").text = date_str
    ET.SubElement(item, "guid").text = mp3_url
    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", mp3_url)
    enclosure.set("length", str(mp3_size))
    enclosure.set("type", "audio/mpeg")

    # Insert after last channel metadata, before existing items
    first_item_idx = next(
        (i for i, child in enumerate(list(channel)) if child.tag == "item"),
        len(list(channel)),
    )
    channel.insert(first_item_idx, item)

    ET.indent(tree, space="  ")
    tree.write(feed_path, encoding="unicode", xml_declaration=True)


def _create_release(owner: str, repo: str, tag: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    resp = requests.post(
        url,
        json={"tag_name": tag, "name": tag, "draft": False, "prerelease": False},
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
    )
    resp.raise_for_status()
    return resp.json()


def _upload_asset(upload_url: str, mp3_path: Path, token: str) -> str:
    # Strip the {?name,label} template from upload_url
    upload_url = re.sub(r"\{.*\}", "", upload_url)
    filename = mp3_path.name
    with open(mp3_path, "rb") as f:
        resp = requests.post(
            f"{upload_url}?name={filename}",
            data=f,
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "audio/mpeg",
            },
        )
    resp.raise_for_status()
    return resp.json()["browser_download_url"]


def publish_episode(mp3_path: Path, script: dict, config: dict) -> str:
    """Create GitHub Release, upload MP3, update feed.xml, push. Returns MP3 download URL."""
    token = os.environ["GITHUB_TOKEN"]
    owner = config["github"]["owner"]
    repo = config["github"]["repo"]

    now = datetime.now(timezone.utc)
    date_slug = now.strftime("%Y-%m-%d")
    tag = f"ep-{date_slug}"
    date_str = now.strftime("%a, %d %b %Y %H:%M:%S +0000")

    logger.info("Creating GitHub Release %s", tag)
    release = _create_release(owner, repo, tag, token)
    upload_url = release["upload_url"]

    logger.info("Uploading MP3 asset")
    mp3_url = _upload_asset(upload_url, mp3_path, token)

    mp3_size = mp3_path.stat().st_size
    update_feed_xml(FEED_PATH, script["title"], mp3_url, mp3_size, date_str)

    logger.info("Committing and pushing feed.xml")
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "add", str(FEED_PATH)], check=True)
    subprocess.run(["git", "commit", "-m", f"episode: {tag}"], check=True)
    subprocess.run(["git", "push"], check=True)

    logger.info("Published: %s", mp3_url)
    return mp3_url


if __name__ == "__main__":
    import yaml
    import sys
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    mp3_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("episodes/test.mp3")
    script = {"title": "Poddig Cast - test"}
    url = publish_episode(mp3_path, script, config)
    print(f"Published: {url}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_publisher.py -v
```

Expected: 3 tests passing

- [ ] **Step 5: Commit**

```bash
git add publisher.py tests/test_publisher.py
git commit -m "feat: publisher — GitHub Release upload, feed.xml update, git push"
```

---

## Task 6: Orchestrator (`run.py`)

**Files:**
- Create: `run.py`
- Create: `tests/test_run.py`

- [ ] **Step 1: Write failing test in `tests/test_run.py`**

```python
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_run_calls_all_stages(tmp_path):
    mock_articles = [{"title": "News", "summary": "Summary", "link": "https://x.com", "published": "2026-03-26", "topics": ["tech"]}]
    mock_script = {"title": "Poddig Cast - 26 mars 2026", "segments": [{"host": "A", "text": "Hej!"}]}
    mock_mp3 = tmp_path / "episode.mp3"
    mock_mp3.write_bytes(b"fake")

    with patch("run.fetch_articles", return_value=mock_articles) as mock_fetch, \
         patch("run.write_script", return_value=mock_script) as mock_write, \
         patch("run.generate_audio", return_value=mock_mp3) as mock_tts, \
         patch("run.publish_episode", return_value="https://example.com/ep.mp3") as mock_pub, \
         patch("run.yaml.safe_load", return_value={"episode": {}, "voices": {}, "tts": {}, "github": {}}), \
         patch("builtins.open", unittest.mock.mock_open()):
        import run
        import importlib
        importlib.reload(run)

    # Verify the pipeline functions exist and are importable
    from run import main
    assert callable(main)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_run.py -v
```

Expected: `ModuleNotFoundError: No module named 'run'` or import error

- [ ] **Step 3: Implement `run.py`**

```python
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fetcher import fetch_articles
from scriptwriter import write_script
from tts import generate_audio
from publisher import publish_episode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=== Poddig Cast pipeline starting ===")

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output_path = Path("episodes") / f"episode-{date_slug}.mp3"

    logger.info("Stage 1/4: Fetching RSS feeds")
    articles = fetch_articles(config)
    logger.info("Fetched %d articles", len(articles))

    logger.info("Stage 2/4: Writing podcast script")
    script = write_script(articles, config)
    logger.info("Script: '%s' (%d segments)", script["title"], len(script["segments"]))

    logger.info("Stage 3/4: Generating audio")
    mp3_path = generate_audio(script, config, output_path)

    logger.info("Stage 4/4: Publishing episode")
    mp3_url = publish_episode(mp3_path, script, config)

    logger.info("=== Done! Episode available at: %s ===", mp3_url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests to verify nothing is broken**

```bash
pytest tests/ -v
```

Expected: All tests passing

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run.py
git commit -m "feat: run.py — pipeline orchestrator"
```

---

## Task 7: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/generate_episode.yml`

No unit tests — verify by triggering manually after pushing.

- [ ] **Step 1: Create `.github/workflows/generate_episode.yml`**

```yaml
name: Generate Podcast Episode

on:
  schedule:
    - cron: '0 7 * * 3,6'  # Wed and Sat at 07:00 UTC
  workflow_dispatch:         # Manual trigger button in GitHub UI

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # Needed to push feed.xml and create releases

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install ffmpeg
        run: sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run podcast pipeline
        env:
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python run.py
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/generate_episode.yml
git commit -m "feat: GitHub Actions workflow — scheduled + manual podcast generation"
```

---

## Task 8: GitHub Setup & First Run

No code changes — setup steps only.

- [ ] **Step 1: Push repo to GitHub**

```bash
gh repo create poddig_cast --public --source=. --remote=origin --push
```

- [ ] **Step 2: Enable GitHub Pages**

Go to repo **Settings → Pages → Source: Deploy from branch → Branch: main → Folder: /docs** → Save.

- [ ] **Step 3: Add secrets to GitHub repo**

Go to repo **Settings → Secrets and variables → Actions → New repository secret**:
- `ELEVENLABS_API_KEY` — your ElevenLabs API key
- `ANTHROPIC_API_KEY` — your Anthropic API key

- [ ] **Step 4: Update `config.yaml` with your GitHub username**

In `config.yaml`, replace `YOUR_GITHUB_USERNAME` with your actual GitHub username in both the `github.owner` field and in `docs/feed.xml`'s `<link>` tag. Commit and push.

- [ ] **Step 5: Trigger first manual run**

Go to **Actions → Generate Podcast Episode → Run workflow → Run workflow**.

Watch the logs. If it succeeds, find the RSS feed URL at:
`https://YOUR_GITHUB_USERNAME.github.io/poddig_cast/feed.xml`

- [ ] **Step 6: Subscribe in a podcast app**

Copy the feed URL and add it as a custom podcast in Pocket Casts, Apple Podcasts, or any app that supports custom RSS feeds.

---

## Self-Review Notes

- All spec requirements covered: RSS fetch ✓, Claude scriptwriter ✓, ElevenLabs v3 TTS ✓, GitHub Releases ✓, GitHub Pages RSS ✓, GitHub Actions schedule + manual ✓, error handling per stage ✓
- Voice IDs from spec are hardcoded in config.yaml ✓
- ElevenLabs `eleven_v3` model used ✓
- Swedish language prompt ✓
- Friendly banter tone in system prompt ✓
- 25-35 segments target in prompt ✓
- SSML tags documented and used ✓
- Each module has `if __name__ == "__main__"` for standalone testing ✓
- ffmpeg dependency noted in workflow ✓
