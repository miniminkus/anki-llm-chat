"""Extract readable text from Anki cards for use as LLM context.

Handles all common Anki field content: HTML, cloze deletions, media
references (sound, images, video), LaTeX, and long text fields.
"""

import html
import re

# Patterns for content that should be stripped from fields
_SOUND_RE = re.compile(r"\[sound:[^\]]+\]")
_IMG_RE = re.compile(r"<img[^>]*>", re.IGNORECASE)
_MEDIA_TAG_RE = re.compile(r"<(?:audio|video|source|object|embed)[^>]*>", re.IGNORECASE)
_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)(?:::[^}]*)?\}\}")
_HTML_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_DIV_RE = re.compile(r"</?div[^>]*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LATEX_RE = re.compile(r"\[latex\].*?\[/latex\]", re.DOTALL | re.IGNORECASE)
_MATHJAX_RE = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Limits to avoid sending excessive content to the API
MAX_FIELD_CHARS = 2000
MAX_TOTAL_CHARS = 6000


def clean_field(raw: str) -> str:
    """Convert a raw Anki field value into clean, readable text.

    Strips HTML, media references, and normalises whitespace.
    Cloze deletions are resolved to show the answer text.
    """
    if not raw:
        return ""

    text = raw

    # Resolve cloze deletions: {{c1::answer::hint}} -> answer
    text = _CLOZE_RE.sub(r"\1", text)

    # Remove media references
    text = _SOUND_RE.sub("", text)
    text = _IMG_RE.sub("", text)
    text = _MEDIA_TAG_RE.sub("", text)

    # Remove LaTeX / MathJax (keep as-is would confuse the LLM)
    text = _LATEX_RE.sub("[formula]", text)
    text = _MATHJAX_RE.sub("[formula]", text)

    # Convert block-level HTML to newlines before stripping tags
    text = _HTML_BR_RE.sub("\n", text)
    text = _HTML_DIV_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)

    # Decode HTML entities (&amp; -> &, &#x4e2d; -> 中, etc.)
    text = html.unescape(text)

    # Normalise whitespace
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    text = text.strip()

    # Truncate overly long fields
    if len(text) > MAX_FIELD_CHARS:
        text = text[:MAX_FIELD_CHARS] + "..."

    return text


def extract_context(card, answer_shown: bool = False) -> str:
    """Build a text summary of the card's fields for the LLM.

    Returns an empty string if the card has no usable text content.
    """
    if card is None:
        return ""

    try:
        note = card.note()
        model = note.model()
    except Exception:
        return ""

    field_names = [f["name"] for f in model.get("flds", [])]
    field_values = note.fields

    parts = []
    for name, raw in zip(field_names, field_values):
        clean = clean_field(raw)
        if clean:
            parts.append(f"{name}: {clean}")

    if not parts:
        return ""

    side = "answer shown" if answer_shown else "question side"
    header = f"[Card – {side}]"

    context = header + "\n" + "\n".join(parts)

    # Hard cap on total context length
    if len(context) > MAX_TOTAL_CHARS:
        context = context[:MAX_TOTAL_CHARS] + "\n..."

    return context
