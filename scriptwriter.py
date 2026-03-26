import json
import logging
import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du är manusförfattare för en svensk nyhetspodcast kallad "Poddig Cast".
Du skriver manus för två programledare: HOST_A (kallas "A") och HOST_B (kallas "B").
Deras ton är vänlig, avslappnad och lättsam — som två vänner som diskuterar nyheter.
De kommenterar, reagerar genuint, och håller samtalet levande och naturligt.
Varje segment ska vara 1-3 meningar max — håll det konversationsnära.
Använd SSML-taggar för naturliga pauser och betoning inuti text-strängen:
  <break time='300ms'/> för paus, <emphasis>ord</emphasis> för betoning,
  <prosody rate='fast'>text</prosody> när en host pratar snabbt/ivrigt.
Returnera ALLTID ett JSON-objekt med denna EXAKTA struktur, inget annat:
{
  "title": "Poddig Cast - [datum på svenska]",
  "segments": [
    {"host": "A", "text": "..."},
    {"host": "B", "text": "..."}
  ]
}
Målet är 25-35 segment (~10 minuter). Börja med en kort intro, ta upp 5-7 nyheter,
avsluta naturligt. Inga reklampausreferenser."""


def write_script(articles: list[dict], config: dict) -> dict:
    """Send articles to Claude, return script as dict with title and segments."""
    # config accepted for interface consistency with other stages; model and
    # prompt values are hardcoded since they are not user-configurable.
    client = anthropic.Anthropic()

    articles_text = "\n\n".join(
        f"[{', '.join(a['topics'])}] {a['title']}\n{a['summary']}"
        for a in articles
    )
    logger.info("Calling Claude API with %d articles", len(articles))

    user_prompt = f"Skriv ett ~10 minuters poddmanus baserat på dessa nyheter:\n\n{articles_text}"

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text

    # Strip markdown code fences if present
    if raw.strip().startswith("```"):
        raw = raw.strip().lstrip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw output:\n{raw}")

    # Validate structure
    if not isinstance(script.get("title"), str) or not isinstance(script.get("segments"), list) or not script["segments"]:
        raise ValueError(f"Claude returned JSON with invalid structure (expected title + non-empty segments): {script}")
    for seg in script["segments"]:
        if seg.get("host") not in ("A", "B") or not isinstance(seg.get("text"), str):
            raise ValueError(f"Claude returned segment with invalid structure: {seg}")

    logger.info("Script generated: '%s' (%d segments)", script.get("title", ""), len(script.get("segments", [])))

    return script


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    articles = [
        {"title": "AI tar över världen", "summary": "OpenAI lanserar ny modell", "link": "https://example.com", "published": "2026-03-26", "topics": ["tech"]},
        {"title": "Trump säger galen sak", "summary": "Presidenten twittrade igen", "link": "https://example.com", "published": "2026-03-26", "topics": ["politics"]},
        {"title": "Ukraine frontlinje", "summary": "Strid nära Kharkiv", "link": "https://example.com", "published": "2026-03-26", "topics": ["ukraine"]},
    ]
    script = write_script(articles, config)
    print(f"Title: {script['title']}")
    print(f"Segments: {len(script['segments'])}")
    for seg in script["segments"][:4]:
        print(f"  [{seg['host']}]: {seg['text'][:80]}...")
