"""Alice skill «Расписание дочки»: answers what the child has on a given day.

Yandex Cloud Function, Python 3.12, entry point `family_skill.index.handler`.
Standard library only.

The schedule is read from SCHEDULE_URL (a JSON file in a private Object Storage
bucket, read with the function's service account token), falling back to the
bundled schedule.json. Format: {"events": [{"day": 0..6 (Mon..Sun),
"start": "HH:MM", "end": "HH:MM", "title": "..."}]}.
"""
import datetime
import json
import os
import time
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_TTL = 300
_cache = {"data": None, "ts": 0.0}

DAY_NAMES = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
# accusative, for "в понедельник", "в среду"
DAY_ACC = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
DAY_STEMS = ["понедельн", "вторн", "сред", "четверг", "пятниц", "суббот", "воскресен"]

HELP_TEXT = (
    "Я подскажу расписание дочки. Спросите: «что сегодня», «что завтра», "
    "«что в четверг», «когда танцы» или «расписание на неделю». "
    "Чтобы выйти, скажите «хватит»."
)


# ---------- data ----------

def load_schedule(cloud_token=None):
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]
    data = None
    url = os.environ.get("SCHEDULE_URL")
    if url:
        headers = {"User-Agent": "alice-family-skill"}
        if cloud_token:
            headers["X-YaCloud-SubjectToken"] = cloud_token
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Failed to load schedule from {url}: {e}")
    if data is None:
        if _cache["data"] is not None:
            return _cache["data"]
        with open(os.path.join(HERE, "schedule.json"), encoding="utf-8") as f:
            data = json.load(f)
    _cache["data"], _cache["ts"] = data, now
    return data


def events_for(data, day):
    return sorted((e for e in data.get("events", []) if e.get("day") == day), key=lambda e: e["start"])


# ---------- phrasing ----------

def on_day(day):
    """«в среду», «во вторник»."""
    return ("во " if day == 1 else "в ") + DAY_ACC[day]


def say_time(hhmm):
    h, m = hhmm.split(":")
    return f"{int(h)}:{m}"


def describe(e):
    return f"с {say_time(e['start'])} до {say_time(e['end'])} {e['title']}"


def day_answer(data, day, label):
    events = events_for(data, day)
    if not events:
        return f"{label} занятий нет, свободный день."
    return f"{label} " + ", потом ".join(describe(e) for e in events) + "."


def week_answer(data):
    parts = []
    for day in range(7):
        events = events_for(data, day)
        if events:
            parts.append(f"{DAY_NAMES[day].capitalize()}: " + ", ".join(describe(e) for e in events) + ".")
    return " ".join(parts) or "В расписании пока пусто."


def activity_answer(data, word):
    events = [e for e in data.get("events", []) if word in e["title"].lower()]
    if not events:
        return None
    events.sort(key=lambda e: (e["day"], e["start"]))
    title = events[0]["title"]
    when = ", ".join(f"{on_day(e['day'])} с {say_time(e['start'])} до {say_time(e['end'])}" for e in events)
    return f"{title[0].upper() + title[1:]}: {when}."


def next_answer(data, now):
    today, hhmm = now.weekday(), now.strftime("%H:%M")
    for offset in range(8):
        day = (today + offset) % 7
        for e in events_for(data, day):
            if offset == 0 and e["end"] <= hhmm:
                continue
            if offset == 0 and e["start"] <= hhmm:
                return f"Сейчас идёт {e['title']}, до {say_time(e['end'])}."
            label = {0: "сегодня", 1: "завтра"}.get(offset, on_day(day))
            return f"Следующее занятие {label} {describe(e)}."
    return "Ближайших занятий нет."


# ---------- dialog ----------

def find_day(text):
    for i, stem in enumerate(DAY_STEMS):
        if stem in text:
            return i
    return None


def answer(text, data, now):
    """Returns the reply text, or None if the request was not understood."""
    t = text.lower().replace("ё", "е")
    if any(w in t for w in ("помощь", "что ты умеешь", "умеешь")):
        return HELP_TEXT
    if any(w in t for w in ("недел", "все расписание", "всё расписание", "полностью")):
        return week_answer(data)
    for word, key in (("танц", "танц"), ("школ", "школ"), ("логоритм", "логоритм"), ("инколинк", "логоритм")):
        if word in t:
            reply = activity_answer(data, key)
            if reply:
                return reply
    if any(w in t for w in ("сейчас", "следующ", "дальше", "ближайш")):
        return next_answer(data, now)
    day = find_day(t)
    if day is not None:
        return day_answer(data, day, on_day(day).capitalize())
    if "послезавтра" in t:
        d = (now.weekday() + 2) % 7
        return day_answer(data, d, f"Послезавтра, {on_day(d)},")
    if "завтра" in t:
        d = (now.weekday() + 1) % 7
        return day_answer(data, d, "Завтра")
    if any(w in t for w in ("сегодня", "расписан", "что у нас", "куда", "забирать", "во сколько")):
        return day_answer(data, now.weekday(), "Сегодня")
    return None


def reply(text, end=False):
    return {"version": "1.0", "response": {"text": text, "tts": text, "end_session": end}}


def handle(event, cloud_token=None):
    req = event.get("request", {}) or {}
    session = event.get("session", {}) or {}
    tz = (event.get("meta") or {}).get("timezone") or "Europe/Moscow"
    try:
        now = datetime.datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.datetime.now(ZoneInfo("Europe/Moscow"))
    text = (req.get("command") or "").strip()
    data = load_schedule(cloud_token)

    if any(w in text.lower() for w in ("хватит", "выход", "стоп", "спасибо")):
        return reply("Хорошо, обращайтесь!", end=True)

    if session.get("new"):
        found = answer(text, data, now) if text else None
        if found:
            # "Алиса, спроси у навыка ..., что сегодня" — answer and finish
            return reply(found, end=True)
        return reply(day_answer(data, now.weekday(), "Привет! Сегодня")
                     + " Можно спросить про завтра, другой день или неделю.")

    found = answer(text, data, now)
    if found:
        return reply(found)
    return reply("Не совсем поняла. Спросите «что сегодня», «что завтра» или «когда танцы».")


def context_token(context):
    token = getattr(context, "token", None)
    return token.get("access_token") if isinstance(token, dict) else None


def handler(event, context=None):
    try:
        return handle(event, cloud_token=context_token(context))
    except Exception as e:
        print(f"Error: {e}")
        return reply("Что-то пошло не так. Попробуйте ещё раз чуть позже.")
