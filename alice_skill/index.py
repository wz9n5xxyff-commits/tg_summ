"""Alice (Yandex Dialogs) skill: reads the weekly "Ясно Понятно" digest aloud.

Deploy as a Yandex Cloud Function (Python 3.10+, entry point `index.handler`).
Standard library only — no requirements.txt needed.

Environment variables:
  DIGEST_URL    URL of alice/digest.json, e.g.
                https://raw.githubusercontent.com/<owner>/tg_summ/main/alice/digest.json
  GITHUB_TOKEN  (optional) token with read access, if the repository is private
"""
import json
import os
import re
import time
import urllib.request

CACHE_TTL = 600  # seconds
MAX_CHARS = 900  # Alice limits text/tts to 1024 chars per reply
_cache = {"data": None, "ts": 0.0}

RUBRICS = {
    "business": ("бизнес", "предприним", "руковод", "стратег"),
    "practice": ("маркет", "контент", "практик", "инструмент"),
    "ai": ("тренд", "нейросет", "модел", "искусствен", "ии", "ai"),
    "think": ("подума", "мысл", "философ", "рефлекс"),
}
RUBRIC_BUTTONS = {
    "business": "Для бизнеса",
    "practice": "Для маркетологов",
    "ai": "ИИ-тренды",
    "think": "На подумать",
}

HELP_TEXT = (
    "Я пересказываю дайджест канала «Ясно Понятно Волкова». "
    "Скажите «что нового» — и я перескажу неделю целиком. "
    "Можно выбрать рубрику: «для бизнеса», «для маркетологов», «ИИ-тренды» или «на подумать». "
    "Ещё могу рассказать последний пост. Чтобы продолжить, скажите «дальше», "
    "чтобы выйти — «хватит»."
)


# ---------- data ----------

def load_digest():
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]
    url = os.environ.get("DIGEST_URL")
    if not url:
        return _cache["data"]
    headers = {"User-Agent": "alice-yasno-skill"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=2) as resp:
            _cache["data"] = json.loads(resp.read().decode("utf-8"))
            _cache["ts"] = now
    except Exception as e:  # keep serving the stale copy if GitHub is slow
        print(f"Failed to load digest: {e}")
    return _cache["data"]


# ---------- speech helpers ----------

def to_tts(text):
    """Small pronunciation fixes for Alice's TTS."""
    text = re.sub(r"\bИИ\b", "И-И", text)
    text = re.sub(r"\bAI\b", "эй-ай", text)
    text = re.sub(r"\bLLM\b", "эл-эл-эм", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def chunk(parts, limit=MAX_CHARS):
    """Groups phrases into replies no longer than `limit` characters."""
    pages, current = [], ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > limit:
            part = part[: limit - 1].rsplit(" ", 1)[0] + "…"
        if current and len(current) + 1 + len(part) > limit:
            pages.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        pages.append(current)
    return pages


def item_phrase(item):
    title = item.get("title", "").rstrip(".")
    summary = item.get("summary", "").strip()
    if summary and summary[-1] not in ".!?…":
        summary += "."
    return f"{title}: {summary}" if title else summary


# ---------- scenarios ----------

def full_digest_pages(data):
    parts = []
    if data.get("intro"):
        parts.append(data["intro"])
    for section in data.get("sections", []):
        parts.append(f"Рубрика «{section['title']}».")
        parts.extend(item_phrase(i) for i in section["items"])
    return chunk(parts)


def section_pages(data, key):
    for section in data.get("sections", []):
        if section["key"] == key:
            parts = [f"{section['title']}."]
            parts.extend(item_phrase(i) for i in section["items"])
            return chunk(parts)
    return None


def latest_post_pages(data):
    post = data.get("latest_post")
    if not post or not post.get("text"):
        return None
    return chunk(["Последний пост в канале.", post["text"]])


def detect_rubric(tokens, command):
    for key, stems in RUBRICS.items():
        for stem in stems:
            if len(stem) <= 2:
                if stem in tokens:
                    return key
            elif stem in command:
                return key
    return None


# ---------- response building ----------

def available_buttons(data, exclude=None):
    titles = ["Что нового"]
    keys = {s["key"] for s in (data or {}).get("sections", [])}
    titles += [t for k, t in RUBRIC_BUTTONS.items() if k in keys and k != exclude]
    titles.append("Последний пост")
    return titles


def reply(text, state=None, buttons=None, end=False, has_more=False):
    if has_more:
        text += " Сказать дальше?"
        buttons = ["Дальше"] + [b for b in (buttons or []) if b != "Дальше"]
    response = {
        "text": text[:1024],
        "tts": to_tts(text)[:1024],
        "end_session": end,
    }
    if buttons:
        response["buttons"] = [{"title": b[:64], "hide": True} for b in buttons[:6]]
    return {
        "version": "1.0",
        "response": response,
        # Alice caps session_state at 1 KB, so only a small pointer is stored
        # here and the page text is rebuilt from the digest on every request.
        "session_state": state or {},
    }


def pages_for(data, mode):
    if mode == "full":
        return full_digest_pages(data)
    if mode == "latest":
        return latest_post_pages(data)
    return section_pages(data, mode)


def paged(data, mode, page=0):
    """Says page `page` of `mode` and remembers the position in the session."""
    pages = pages_for(data, mode) or []
    if page >= len(pages):
        return reply(
            "Это всё. Хотите послушать другую рубрику или последний пост?",
            buttons=available_buttons(data),
        )
    exclude = mode if mode in RUBRIC_BUTTONS else None
    return reply(
        pages[page],
        state={"mode": mode, "page": page},
        buttons=available_buttons(data, exclude),
        has_more=page + 1 < len(pages),
    )


def handle(event):
    request = event.get("request", {})
    session = event.get("session", {})
    state = event.get("state", {}).get("session", {}) or {}
    command = (request.get("command") or "").lower().replace("ё", "е")
    tokens = set(request.get("nlu", {}).get("tokens", []) or re.findall(r"\w+", command))

    data = load_digest()

    if any(w in tokens for w in ("хватит", "выход", "выйти", "стоп", "пока")):
        return reply("Хорошо, до встречи! Новый дайджест выходит по воскресеньям.", end=True)

    if not data or not data.get("sections"):
        return reply(
            "Дайджест пока не готов. Он появляется по воскресеньям вечером, загляните позже.",
            end=True,
        )

    if session.get("new") and not command:
        greeting = "Привет! Это дайджест канала «Ясно Понятно Волкова». "
        if data.get("intro"):
            greeting += "Коротко о неделе: " + data["intro"] + " "
        greeting += "Пересказать всё, выбрать рубрику или рассказать последний пост?"
        return reply(chunk([greeting])[0], buttons=available_buttons(data))

    if any(w in command for w in ("помощ", "умеешь", "что ты можешь")):
        return reply(HELP_TEXT, buttons=available_buttons(data))

    mode, page = state.get("mode"), int(state.get("page", 0) or 0)

    if any(w in command for w in ("повтор", "еще раз")) and mode:
        return paged(data, mode, page)

    if tokens & {"дальше", "далее", "продолжи", "продолжай", "да", "давай", "еще"} and mode:
        return paged(data, mode, page + 1)

    if "последн" in command or "свеж" in command:
        if latest_post_pages(data):
            return paged(data, "latest")
        return reply("Последний пост пока не загружен.", buttons=available_buttons(data))

    rubric = detect_rubric(tokens, command)
    if rubric:
        if section_pages(data, rubric):
            return paged(data, rubric)
        return reply(
            f"На этой неделе в рубрике «{RUBRIC_BUTTONS[rubric]}» ничего не было. Выбрать другую?",
            buttons=available_buttons(data, exclude=rubric),
        )

    if any(w in command for w in ("нов", "дайджест", "недел", "все", "расскажи", "перескажи")) or \
            tokens & {"да", "давай"}:
        return paged(data, "full")

    return reply(
        "Не совсем поняла. Скажите «что нового», назовите рубрику или попросите последний пост.",
        buttons=available_buttons(data),
    )


def handler(event, context=None):
    """Entry point for Yandex Cloud Functions."""
    try:
        return handle(event)
    except Exception as e:
        print(f"Skill error: {e}")
        return reply("Ой, что-то сломалось. Попробуйте ещё раз чуть позже.")
