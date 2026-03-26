import io
import logging
import os
from pathlib import Path

import requests
from pydub import AudioSegment

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


def _tts_segment(text: str, voice_id: str, model: str, output_format: str, api_key: str) -> bytes:
    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}?output_format={output_format}"
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


REACTION_OVERLAP_MS = 600  # how far from end of current cursor to start a reaction


def generate_audio(script: dict, config: dict, output_path: Path) -> Path:
    """Generate merged MP3 from script segments using ElevenLabs v3."""
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_map = {
        "A": config["voices"]["host_a"],
        "B": config["voices"]["host_b"],
    }
    model = config["tts"]["model"]
    output_format = config["tts"]["output_format"]
    pause_ms = 150

    # Generate all audio chunks first
    chunks = []
    for i, segment in enumerate(script["segments"]):
        host = segment["host"]
        text = segment["text"]
        voice_id = voice_map[host]
        is_reaction = segment.get("reaction", False)

        logger.info("TTS segment %d/%d [Host %s%s]: %s...", i + 1, len(script["segments"]), host, " reaction" if is_reaction else "", text[:50])

        audio_bytes = _tts_segment(text, voice_id, model, output_format, api_key)
        chunk = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        chunks.append((segment, chunk))

    # Build timeline: reactions overlay the tail of the previous main segment
    placements = []  # list of (start_ms, chunk)
    cursor = 0  # end of last non-reaction segment in ms

    for segment, chunk in chunks:
        is_reaction = segment.get("reaction", False)
        if is_reaction:
            start = max(0, cursor - REACTION_OVERLAP_MS)
            placements.append((start, chunk))
        else:
            faded = chunk.fade_in(10).fade_out(10)
            placements.append((cursor, faded))
            cursor += len(faded) + pause_ms

    # Mix all placements into a single track
    total_length = max(start + len(c) for start, c in placements)
    combined = AudioSegment.silent(duration=total_length)
    for start_ms, chunk in placements:
        combined = combined.overlay(chunk, position=start_ms)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output_path), format="mp3")
    logger.info("Episode saved to %s (%.1f seconds)", output_path, len(combined) / 1000)
    return output_path


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    test_script = {
        "title": "Test",
        "segments": [{"host": "A", "text": "Hej, det här är ett test av ljudgenerering."}],
    }
    out = generate_audio(test_script, config, Path("episodes/test.mp3"))
    print(f"Output: {out}")
