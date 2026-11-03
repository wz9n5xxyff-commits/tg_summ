"""Converts the HTML Telegram digest into structured data for the Alice skill.

The weekly GitHub Action calls `export_for_alice(...)` after the digest is
generated; the result is committed to `alice/digest.json`, which the Alice
skill (alice_skill/index.py) reads. Parsing is deterministic, so no extra
Gemini call is needed.
"""
import html
import json
import os
import re
from datetime import datetime, timezone

# Emoji in the rubric header -> stable section key (see SYSTEM_PROMPT in ai_writer.py)
SECTION_KEYS = {
    "🎙": "intro",
    "💼": "business",
    "🛠": "practice",
    "🧠": "ai",
    "☕": "think",
}

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alice", "digest.json")

_TAG_RE = re.compile(r"<[^>]+>")
_LINK_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>.*?</a>', re.IGNORECASE | re.DOTALL)
_BOLD_RE = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿️‍]+"
)


def strip_html(text):
    return html.unescape(_TAG_RE.sub("", text)).strip()


def clean_spoken(text):
    """Removes emoji and stray markup so the text reads well aloud."""
    text = strip_html(text)
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    return re.sub(r"\s+", " ", text).strip(" —-–")


def _section_key(line):
    for emoji, key in SECTION_KEYS.items():
        if line.startswith(emoji):
            return key
    return None


def _clean_title(raw_title):
    title = clean_spoken(raw_title)
    # Drop the "(Стратегия)" style suffix from rubric headers
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()


def parse_digest(digest_html):
    """Parses the digest into {"intro": str, "sections": [...]}."""
    intro_lines = []
    sections = []
    current = None

    for raw_line in digest_html.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        key = _section_key(line)
        if key:
            bold = _BOLD_RE.search(line)
            title = _clean_title(bold.group(1) if bold else line)
            if key == "intro":
                current = "intro"
            else:
                current = {"key": key, "title": title, "items": []}
                sections.append(current)
            continue

        if current == "intro":
            intro_lines.append(clean_spoken(line))
            continue

        if isinstance(current, dict) and line.startswith(("•", "-", "*")):
            link_match = _LINK_RE.search(line)
            link = link_match.group(1) if link_match else ""
            body = _LINK_RE.sub("", line).lstrip("•-* ").strip()
            bold = _BOLD_RE.match(body)
            if bold:
                title = clean_spoken(bold.group(1))
                summary = clean_spoken(body[bold.end():])
            else:
                title, summary = "", clean_spoken(body)
            current["items"].append({"title": title, "summary": summary, "link": link})

    return {
        "intro": " ".join(l for l in intro_lines if l),
        "sections": [s for s in sections if s["items"]],
    }


def _short_text(text, limit=600):
    """Cuts text on a sentence boundary so it fits into a voice reply."""
    text = re.sub(r"\s+", " ", _EMOJI_RE.sub("", text)).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > limit // 3 else cut.rsplit(" ", 1)[0] + "…").strip()


def build_alice_data(digest_html, posts):
    data = parse_digest(digest_html)
    data["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["latest_post"] = None
    if posts:
        latest = max(posts, key=lambda p: p["date"])
        date = latest["date"]
        data["latest_post"] = {
            "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
            "link": latest.get("link", ""),
            "text": _short_text(latest.get("text", "")),
        }
    return data


def export_for_alice(digest_html, posts, path=DEFAULT_PATH):
    data = build_alice_data(digest_html, posts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data
