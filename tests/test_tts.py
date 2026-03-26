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
         patch("tts.AudioSegment.silent", return_value=mock_audio), \
         patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
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
