# Poddig Cast — Design Spec
**Date:** 2026-03-26

## Overview

Poddig Cast is an automatically generated Swedish news podcast. A GitHub Actions pipeline fetches RSS news feeds, uses Claude to write a dynamic two-host script, generates audio via ElevenLabs v3, and publishes the episode as a GitHub Release with an RSS feed hosted on GitHub Pages. Episodes run on a schedule (Wed + Sat) or can be manually triggered.

---

## Goals

- ~10 minute Swedish podcast, 1-2 episodes per week
- Two hosts with friendly, bantering conversational style
- Covers: tech, Ukraine war, Trump/US politics, major world news
- Subscribable in any podcast app via RSS
- No local environment required — runs entirely in GitHub Actions

---

## Architecture

The pipeline has four stages, each a separate Python module. GitHub Actions orchestrates them sequentially. If a run fails, re-trigger manually from the GitHub UI.

```
poddig_cast/
├── .github/
│   └── workflows/
│       └── generate_episode.yml   # Cron + manual trigger
├── config.yaml                    # Feeds, voices, episode settings
├── run.py                         # Entry point — runs all stages in order
├── fetcher.py                     # Fetch & score RSS articles
├── scriptwriter.py                # Claude API → Swedish podcast script (JSON)
├── tts.py                         # ElevenLabs v3 → MP3 segments → merged episode
├── publisher.py                   # GitHub Release (MP3) + feed.xml update + commit
├── requirements.txt
├── episodes/                      # Gitignored — local output only
└── docs/
    └── feed.xml                   # GitHub Pages RSS feed
```

---

## Pipeline Stages

### 1. Fetcher (`fetcher.py`)
- Pulls configured RSS feeds
- Parses titles, summaries, publication dates
- Scores and filters articles by topic relevance (tech, ukraine, politics, world)
- Returns top 7 stories as structured data for the scriptwriter
- If a feed fails: skip it, log warning, continue with remaining feeds
- If all feeds fail: abort run with error

### 2. Scriptwriter (`scriptwriter.py`)
- Sends top stories to Claude API with a Swedish-language prompt
- Instructs Claude to write a ~10 min podcast script for two hosts (Host A + Host B)
- Hosts have a friendly, casual, bantering tone — like two friends discussing the news
- Output is structured JSON. The `text` field contains the full SSML-formatted string passed directly to ElevenLabs:

```json
{
  "title": "Poddig Cast - 26 mars 2026",
  "segments": [
    { "host": "A", "text": "Hallå och välkommen till Poddig Cast!<break time='300ms'/>" },
    { "host": "B", "text": "Ja hej! Idag har vi en <emphasis>helt galen</emphasis> nyhetsvecka..." }
  ]
}
```

- Target: 25-35 segments = ~10 minutes at natural speaking pace
- Each segment is 1-3 sentences max for natural back-and-forth rhythm
- SSML tags used: `<break>`, `<emphasis>`, `<prosody rate="fast/slow">`

### 3. TTS (`tts.py`)
- Iterates over segments from the script JSON
- Calls ElevenLabs API for each segment with the correct voice ID and `model_id: "eleven_v3"`
- Host A voice: `6eknYWL7D5Z4nRkDy15t`
- Host B voice: `7UMEOkIJdI4hjmR2SWNq`
- Downloads each audio chunk as MP3
- Merges all chunks in order using `pydub` into one final episode MP3
- Output format: `mp3_44100_128`

### 4. Publisher (`publisher.py`)
- Creates a GitHub Release tagged with the episode date (e.g. `ep-2026-03-26`)
- Uploads the merged MP3 as a release asset
- Updates `docs/feed.xml` with a new `<item>` entry pointing to the release asset URL
- Commits and pushes `feed.xml` back to `main`
- GitHub Pages serves `docs/feed.xml` as the public podcast RSS URL

---

## Configuration (`config.yaml`)

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
  - url: "https://feeds.feedburner.com/TechCrunch"
    topics: [tech]
  - url: "https://www.svt.se/nyheter/rss.xml"
    topics: [sweden, world]

episode:
  target_duration_minutes: 10
  max_stories: 7
  language: "sv"

github:
  repo: "poddig_cast"
  pages_branch: "main"
```

---

## GitHub Actions Workflow

**File:** `.github/workflows/generate_episode.yml`

- **Schedule:** `cron: '0 7 * * 3,6'` — Wednesday and Saturday at 07:00 UTC
- **Manual trigger:** `workflow_dispatch` — button in GitHub Actions UI
- **Secrets required:**
  - `ELEVENLABS_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GITHUB_TOKEN` (built-in)
- **Runner:** `ubuntu-latest`
- **Steps:** checkout → setup Python → install requirements → run `python run.py`

---

## GitHub Pages & RSS

- GitHub Pages serves the `docs/` folder on `main`
- RSS feed URL: `https://<your-github-username>.github.io/poddig_cast/feed.xml` (set your username in `config.yaml`)
- Subscribe to this URL in any podcast app (Pocket Casts, Apple Podcasts, Spotify, etc.)
- MP3 files are hosted as GitHub Release assets — no repo bloat

---

## Error Handling

| Stage | Failure | Behaviour |
|---|---|---|
| Fetcher | One feed down | Skip feed, log warning, continue |
| Fetcher | All feeds down | Abort run with error |
| Scriptwriter | Claude API error | Abort run — no credits spent |
| TTS | ElevenLabs error | Abort run — re-trigger manually to retry |
| Publisher | GitHub push error | MP3 exists in runner — re-trigger publish |

---

## Testing

Each module has a `if __name__ == "__main__"` block for standalone testing:

- **Fetcher:** run against one RSS feed, verify parsed article output
- **Scriptwriter:** run with 2-3 hardcoded headlines, verify JSON structure and segment count
- **TTS:** run with one short segment to verify ElevenLabs response (minimal credit cost)
- **Publisher:** run with a dummy MP3 to verify Release creation and `feed.xml` update
- **Full pipeline:** manual end-to-end run before enabling the schedule

---

## Out of Scope

- Transcript/show notes generation
- Multi-language support
- Listener analytics
- Audio post-processing (normalization, music, jingles)
