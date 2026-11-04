import datetime
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from family_skill import index as f  # noqa: E402

DATA = f.load_schedule()
MONDAY = datetime.datetime(2026, 11, 9, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))


def test_today_and_tomorrow():
    assert f.answer("что сегодня", DATA, MONDAY) == "Сегодня с 17:00 до 19:00 логоритмика в Инколинке."
    assert f.answer("а завтра?", DATA, MONDAY) == "Завтра с 16:30 до 17:30 танцы."


def test_weekday_and_free_day():
    assert f.answer("что в четверг", DATA, MONDAY).startswith("В четверг с 16:30 до 17:20 танцы, потом")
    assert "свободный день" in f.answer("что в среду", DATA, MONDAY)


def test_activity():
    assert f.answer("когда танцы", DATA, MONDAY) == \
        "Танцы: во вторник с 16:30 до 17:30, в четверг с 16:30 до 17:20."
    assert f.answer("логоритмика", DATA, MONDAY).startswith("Логоритмика в Инколинке")


def test_next_event_in_progress():
    now = MONDAY.replace(hour=18)
    assert f.answer("что сейчас", DATA, now) == "Сейчас идёт логоритмика в Инколинке, до 19:00."


def test_one_shot_request_ends_session():
    resp = f.handle({"session": {"new": True}, "request": {"command": "что в субботу"}})
    assert resp["response"]["end_session"] is True
    assert "школа" in resp["response"]["text"]


def test_unknown_phrase():
    resp = f.handle({"session": {"new": False}, "request": {"command": "абракадабра"}})
    assert "Не совсем поняла" in resp["response"]["text"]
