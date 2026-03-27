import io
import logging
import os
from pathlib import Path

import requests
from pydub import AudioSegment

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


def _get_voice_config(host_config):
    """Extract voice config, supporting both string (legacy) and dict formats."""
    if isinstance(host_config, str):
        return {"voice_id": host_config, "stability": 0.5, "similarity_boost": 0.75}
    return host_config


def _tts_segment(text: str, voice_id: str, model: str, output_format: str, api_key: str,
                 stability: float = 0.5, similarity_boost: float = 0.75,
                 previous_text: str = None, next_text: str = None) -> bytes:
    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}?output_format={output_format}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs API error {response.status_code}: {response.text}")
    return response.content


PAUSE_MAP = {
    "none": 0,
    "short": 100,
    "medium": 250,
    "long": 500,
}

DEFAULT_OVERLAP_MS = 600
MAX_OVERLAP_RATIO = 0.4  # cap overlap at 40% of previous segment duration
DUCK_DB = 3  # volume reduction in dB during reaction overlaps


def generate_audio(script: dict, config: dict, output_path: Path) -> Path:
    """Generate merged MP3 from script segments using ElevenLabs v3."""
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_configs = {
        "A": _get_voice_config(config["voices"]["host_a"]),
        "B": _get_voice_config(config["voices"]["host_b"]),
    }
    model = config["tts"]["model"]
    output_format = config["tts"]["output_format"]
    segments = script["segments"]

    # Generate all audio chunks with context passing
    chunks = []
    for i, segment in enumerate(segments):
        host = segment["host"]
        text = segment["text"]
        vc = voice_configs[host]
        is_reaction = segment.get("reaction", False)

        # Find nearest same-host segments for context
        prev_text = None
        for j in range(i - 1, -1, -1):
            if segments[j]["host"] == host:
                prev_text = segments[j]["text"]
                break
        next_text = None
        for j in range(i + 1, len(segments)):
            if segments[j]["host"] == host:
                next_text = segments[j]["text"]
                break

        logger.info("TTS segment %d/%d [Host %s%s]: %s...", i + 1, len(segments), host, " reaction" if is_reaction else "", text[:50])

        audio_bytes = _tts_segment(
            text, vc["voice_id"], model, output_format, api_key,
            stability=vc["stability"], similarity_boost=vc["similarity_boost"],
            previous_text=prev_text, next_text=next_text,
        )
        chunk = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        chunks.append((segment, chunk))

    # Pass 1: place non-reaction segments into timeline
    main_placements = []  # (start_ms, chunk)
    reaction_placements = []  # (start_ms, chunk)
    cursor = 0
    prev_main_duration = 0

    for segment, chunk in chunks:
        is_reaction = segment.get("reaction", False)
        if is_reaction:
            # Cap overlap at 40% of previous main segment
            overlap = min(DEFAULT_OVERLAP_MS, int(prev_main_duration * MAX_OVERLAP_RATIO))
            start = max(0, cursor - overlap)
            faded = chunk.fade_in(5).fade_out(5)
            reaction_placements.append((start, faded))
        else:
            faded = chunk.fade_in(10).fade_out(10)
            main_placements.append((cursor, faded))
            prev_main_duration = len(faded)
            pause_ms = PAUSE_MAP.get(segment.get("pause_hint", "medium"), 250)
            cursor += len(faded) + pause_ms

    # Build main track from non-reaction segments
    all_placements = main_placements + reaction_placements
    total_length = max(start + len(c) for start, c in all_placements) if all_placements else 0
    combined = AudioSegment.silent(duration=total_length)

    for start_ms, chunk in main_placements:
        combined = combined.overlay(chunk, position=start_ms)

    # Pass 2: overlay reactions with volume ducking
    for start_ms, chunk in reaction_placements:
        dur = len(chunk)
        overlap_end = min(start_ms + dur, len(combined))
        if start_ms < overlap_end:
            # Duck the main track at the overlap region
            before = combined[:start_ms]
            ducked = combined[start_ms:overlap_end] - DUCK_DB
            after = combined[overlap_end:]
            combined = before + ducked + after
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
