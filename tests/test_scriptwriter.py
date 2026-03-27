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


def test_strips_markdown_code_fences():
    fenced = "```json\n" + json.dumps(VALID_SCRIPT) + "\n```"
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=fenced)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        script = write_script(MOCK_ARTICLES, MOCK_CONFIG)
    assert script["title"] == VALID_SCRIPT["title"]
    assert len(script["segments"]) == len(VALID_SCRIPT["segments"])


def test_strips_ssml_tags():
    script_with_ssml = {
        "title": "Poddig Cast - 26 mars 2026",
        "segments": [
            {"host": "A", "text": "Hallå <break time='300ms'/> och välkommen!"},
            {"host": "B", "text": "Det var <emphasis>helt sjukt</emphasis>."},
            {"host": "A", "text": "<prosody rate='fast'>Snabbt snabbt</prosody> ja."},
        ],
    }
    mock_client = _make_mock_client(script_with_ssml)
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        script = write_script(MOCK_ARTICLES, MOCK_CONFIG)
    assert script["segments"][0]["text"] == "Hallå  och välkommen!"
    assert script["segments"][1]["text"] == "Det var helt sjukt."
    assert script["segments"][2]["text"] == "Snabbt snabbt ja."


def test_accepts_valid_pause_hint():
    script_with_hints = {
        "title": "Poddig Cast - 26 mars 2026",
        "segments": [
            {"host": "A", "text": "Hej!", "pause_hint": "long"},
            {"host": "B", "text": "Hej!", "pause_hint": "short"},
        ],
    }
    mock_client = _make_mock_client(script_with_hints)
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        script = write_script(MOCK_ARTICLES, MOCK_CONFIG)
    assert script["segments"][0]["pause_hint"] == "long"


def test_raises_on_invalid_pause_hint():
    script_bad_hint = {
        "title": "Poddig Cast - 26 mars 2026",
        "segments": [
            {"host": "A", "text": "Hej!", "pause_hint": "superlong"},
        ],
    }
    mock_client = _make_mock_client(script_bad_hint)
    with patch("scriptwriter.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ValueError, match="pause_hint"):
            write_script(MOCK_ARTICLES, MOCK_CONFIG)
