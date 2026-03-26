import logging
import feedparser

logger = logging.getLogger(__name__)


def fetch_articles(config: dict) -> list[dict]:
    """Fetch RSS feeds, return top N articles as dicts."""
    max_stories = config["episode"]["max_stories"]
    all_articles = []
    successful_feeds = 0

    for feed_config in config["feeds"]:
        url = feed_config["url"]
        topics = feed_config["topics"]

        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("Skipping feed %s: %s", url, feed.bozo_exception)
            continue

        successful_feeds += 1
        for entry in feed.entries[:3]:
            all_articles.append({
                "title": getattr(entry, "title", ""),
                "summary": getattr(entry, "summary", ""),
                "link": getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
                "topics": topics,
            })

    if successful_feeds == 0:
        raise RuntimeError("All RSS feeds failed — cannot generate episode")

    return all_articles[:max_stories]


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    articles = fetch_articles(config)
    for a in articles:
        print(f"[{', '.join(a['topics'])}] {a['title']}")
