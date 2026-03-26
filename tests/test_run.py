import importlib
import sys
import unittest.mock
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_main_calls_all_stages(tmp_path):
    mock_articles = [{"title": "News", "summary": "Summary", "link": "https://x.com", "published": "2026-03-26", "topics": ["tech"]}]
    mock_script = {"title": "Poddig Cast - 26 mars 2026", "segments": [{"host": "A", "text": "Hej!"}]}
    mock_mp3 = tmp_path / "episode.mp3"
    mock_mp3.write_bytes(b"fake")
    mock_config = {"episode": {}, "voices": {}, "tts": {}, "github": {}}

    with patch("fetcher.fetch_articles", return_value=mock_articles) as mock_fetch, \
         patch("scriptwriter.write_script", return_value=mock_script) as mock_write, \
         patch("tts.generate_audio", return_value=mock_mp3) as mock_tts, \
         patch("publisher.publish_episode", return_value="https://example.com/ep.mp3") as mock_pub, \
         patch("builtins.open", unittest.mock.mock_open(read_data=b"")), \
         patch("yaml.safe_load", return_value=mock_config):
        # Remove cached run module if it exists
        if "run" in sys.modules:
            del sys.modules["run"]
        import run
        run.main()

    mock_fetch.assert_called_once_with(mock_config)
    mock_write.assert_called_once_with(mock_articles, mock_config)
    mock_tts.assert_called_once()
    mock_pub.assert_called_once()
