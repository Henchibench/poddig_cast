import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from tts import generate_audio, _get_voice_config


MOCK_CONFIG = {
    "voices": {
        "host_a": {
            "voice_id": "6eknYWL7D5Z4nRkDy15t",
            "stability": 0.40,
            "similarity_boost": 0.70,
        },
        "host_b": {
            "voice_id": "7UMEOkIJdI4hjmR2SWNq",
            "stability": 0.35,
            "similarity_boost": 0.65,
        },
    },
    "tts": {
        "model": "eleven_v3",
        "output_format": "mp3_44100_128",
    },
}

MOCK_CONFIG_LEGACY = {
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


def _make_mock_audio():
    """Create a MagicMock that supports pydub-style operations."""
    mock_audio = MagicMock()
    mock_audio.__len__ = MagicMock(return_value=2000)
    mock_audio.__add__ = MagicMock(return_value=mock_audio)
    mock_audio.__sub__ = MagicMock(return_value=mock_audio)
    mock_audio.__getitem__ = MagicMock(return_value=mock_audio)
    mock_audio.overlay = MagicMock(return_value=mock_audio)
    mock_audio.fade_in = MagicMock(return_value=mock_audio)
    mock_audio.fade_out = MagicMock(return_value=mock_audio)
    mock_audio.export = MagicMock()
    return mock_audio


def test_calls_elevenlabs_for_each_segment(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    assert mock_post.call_count == len(MOCK_SCRIPT["segments"])


def test_uses_correct_voice_per_host(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
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

    with patch("tts.requests.post", return_value=mock_response), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        with pytest.raises(RuntimeError, match="ElevenLabs API error"):
            generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")


def test_uses_output_format_in_url(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    url_called = mock_post.call_args_list[0][0][0]
    assert "mp3_44100_128" in url_called


def test_passes_per_host_voice_settings(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    # Host A's call should use stability=0.40
    payload_a = mock_post.call_args_list[0][1]["json"]
    assert payload_a["voice_settings"]["stability"] == 0.40
    assert payload_a["voice_settings"]["similarity_boost"] == 0.70

    # Host B's call should use stability=0.35
    payload_b = mock_post.call_args_list[1][1]["json"]
    assert payload_b["voice_settings"]["stability"] == 0.35
    assert payload_b["voice_settings"]["similarity_boost"] == 0.65


def test_legacy_string_config_format(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG_LEGACY, tmp_path / "episode.mp3")

    # Should use default stability/similarity_boost
    payload = mock_post.call_args_list[0][1]["json"]
    assert payload["voice_settings"]["stability"] == 0.5
    assert payload["voice_settings"]["similarity_boost"] == 0.75


def test_passes_context_text(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3fake_mp3_bytes"

    mock_audio = _make_mock_audio()

    with patch("tts.requests.post", return_value=mock_response) as mock_post, \
         patch("tts.AudioSegment.from_file", return_value=mock_audio), \
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        generate_audio(MOCK_SCRIPT, MOCK_CONFIG, tmp_path / "episode.mp3")

    # Third segment (host A, index 2) should have previous_text from first segment (host A, index 0)
    payload_third = mock_post.call_args_list[2][1]["json"]
    assert payload_third["previous_text"] == "Hallå och välkommen!"


def test_get_voice_config_legacy():
    result = _get_voice_config("some_voice_id")
    assert result == {"voice_id": "some_voice_id", "stability": 0.5, "similarity_boost": 0.75}


def test_get_voice_config_dict():
    cfg = {"voice_id": "abc", "stability": 0.3, "similarity_boost": 0.6}
    assert _get_voice_config(cfg) == cfg
