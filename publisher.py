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

ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")


def update_feed_xml(feed_path: Path, title: str, mp3_url: str, mp3_size: int, date_str: str) -> None:
    """Insert a new <item> at the top of the RSS feed's <channel>."""
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
    file_size = mp3_path.stat().st_size
    with open(mp3_path, "rb") as f:
        resp = requests.post(
            f"{upload_url}?name={filename}",
            data=f,
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "audio/mpeg",
                "Content-Length": str(file_size),
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

    mp3_size = mp3_path.stat().st_size
    logger.info("Uploading MP3 asset")
    mp3_url = _upload_asset(upload_url, mp3_path, token)

    update_feed_xml(FEED_PATH, script.get("title", f"Poddig Cast - {date_slug}"), mp3_url, mp3_size, date_str)

    logger.info("Committing and pushing feed.xml")
    subprocess.run(["git", "config", "--local", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "config", "--local", "user.name", "github-actions[bot]"], check=True)
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
