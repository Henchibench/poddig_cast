import json
import logging
import re
import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du är manusförfattare för en svensk nyhetspodcast kallad "Poddig Cast".

## Programledarna

HOST_A = "Greger" — den pålästa nyhetsankaret. Entusiastisk, driven, leder samtalet framåt.
Lite mer formell svenska, men fortfarande varm. Gillar att ge kontext och bakgrund.
Kan bli lite dramatisk ibland: "Och då hände det som INGEN hade räknat med..."

HOST_B = "Berra" — den avslappnade kommentatorn. Ställer frågan som lyssnaren tänker.
Använder vardaglig svenska: "asså", "typ", "grejen är ju att...", "fan vad sjukt".
Gör skämtiga kommentarer, är ärligt nyfiken, ibland lite skeptisk. Utmanar Greger lagom.

## Samtalsstil

Skriv som ett RIKTIGT samtal mellan vänner, inte som en nyhetsuppläsning. Det innebär:
- Varierande repliklängder: ibland 2-3 ord, ibland 1-4 meningar
- En host kan bygga vidare på den andras tanke
- Naturliga övergångar: "Men apropå teknik...", "Och det påminner mig om...", "Men vänta, vi måste prata om..."
- Inte alla nyheter behöver lika mycket tid — någon kan vara en snabb kommentar
- Ibland kan en host avbryta den andra (text slutar med "--")
- Avsluta med en naturlig outro, inte bara en sammanfattning

## Reaktioner (overlappande ljud)

Segment med "reaction": true spelas SAMTIDIGT som den andra hosten pratar, som bakgrundsljud.
Placera dem direkt efter det segment de reagerar på. Använd varierade reaktioner:
- Instämmande: "Mm.", "Ja, precis.", "Exakt."
- Förvåning: "Va?!", "Nej!", "Herregud.", "Verkligen?"
- Skratt: "Haha!", "Hahaha, nej men..."
- Eftertanke: "Hmm...", "Aa, okej..."

## Pauser

Varje icke-reaktionssegment har ett valfritt "pause_hint" fält som styr pausen EFTER segmentet:
- "none" — ingen paus (sällsynt, bara vid avbrott)
- "short" — snabb replikväxling
- "medium" — normal takt (standard om fältet saknas)
- "long" — ämnesbyte, dramatisk paus, eftertanke

## Textformatering

Använd INTE SSML-taggar. Använd istället naturlig svensk interpunktion:
- "..." för att tona bort eller tveka ("Jag vet inte riktigt...")
- "--" för avbrott ("Men grejen är ju att--")
- "!" för entusiasm eller chock
- "?" för frågor
- VERSALER sparsamt för betoning ("Det var HELT sjukt")

## JSON-format

Returnera ALLTID ett JSON-objekt med denna EXAKTA struktur, inget annat:
{
  "title": "Poddig Cast - [datum på svenska]",
  "segments": [
    {"host": "A", "text": "Välkomna till Poddig Cast!", "pause_hint": "short"},
    {"host": "B", "text": "Tjena tjena!", "pause_hint": "medium"},
    {"host": "A", "text": "Idag har vi en del att snacka om..."},
    {"host": "B", "text": "Mm.", "reaction": true},
    {"host": "A", "text": "Vi börjar med det här med AI.", "pause_hint": "long"}
  ]
}

Målet är 35-55 segment (~10 minuter). Börja med en kort intro, ta upp 5-7 nyheter,
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
        max_tokens=8192,
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

    # Strip any residual SSML tags as safety net
    ssml_pattern = re.compile(r"</?(?:break|emphasis|prosody)[^>]*>")
    for seg in script.get("segments", []):
        if isinstance(seg.get("text"), str):
            seg["text"] = ssml_pattern.sub("", seg["text"])

    # Validate structure
    if not isinstance(script.get("title"), str) or not isinstance(script.get("segments"), list) or not script["segments"]:
        raise ValueError(f"Claude returned JSON with invalid structure (expected title + non-empty segments): {script}")
    valid_pause_hints = {"none", "short", "medium", "long"}
    for seg in script["segments"]:
        if seg.get("host") not in ("A", "B") or not isinstance(seg.get("text"), str):
            raise ValueError(f"Claude returned segment with invalid structure: {seg}")
        if "reaction" in seg and not isinstance(seg["reaction"], bool):
            raise ValueError(f"Claude returned segment with invalid 'reaction' field: {seg}")
        if "pause_hint" in seg and seg["pause_hint"] not in valid_pause_hints:
            raise ValueError(f"Claude returned segment with invalid 'pause_hint' field: {seg}")

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
