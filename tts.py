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
