import logging
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
