import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "alice_skill"))

import index as skill  # noqa: E402
from voice_export import build_alice_data  # noqa: E402

SAMPLE_DIGEST = """🎙️ <b>Интро (Главный вайб недели)</b>
Неделя получилась про агентов. Я много тестировала и делюсь выводами.

💼 <b>Для предпринимателей и руководителей (Стратегия)</b>
• <b>Агенты в продажах</b> — как ИИ-агент разбирает входящие заявки. <a href="https://t.me/yasnovolkova/700">Читать пост</a>

🧠 <b>ИИ-тренды (Для энтузиастов)</b>
• <b>Новая модель</b> — что умеет свежий релиз &amp; где он полезен. <a href="https://t.me/yasnovolkova/701">Читать пост</a>
• <b>Голосовые ИИ</b> — почему голос снова в тренде. <a href="https://t.me/yasnovolkova/702">Читать пост</a>
"""

POSTS = [
    {"date": datetime(2026, 10, 30), "link": "https://t.me/yasnovolkova/700", "text": "Старый пост."},
    {"date": datetime(2026, 11, 1), "link": "https://t.me/yasnovolkova/702", "text": "Свежий пост про голос 🎤. Второе предложение."},
]


def make_event(command="", new=False, state=None):
    return {
        "request": {"command": command, "nlu": {"tokens": command.lower().split()}},
        "session": {"new": new},
        "state": {"session": state or {}},
        "version": "1.0",
    }


def setup_module():
    skill._cache["data"] = build_alice_data(SAMPLE_DIGEST, POSTS)
    skill._cache["ts"] = 1e12  # never expires in tests


def test_parse_digest():
    data = build_alice_data(SAMPLE_DIGEST, POSTS)
    assert data["intro"].startswith("Неделя получилась про агентов")
    assert [s["key"] for s in data["sections"]] == ["business", "ai"]
    assert data["sections"][0]["title"] == "Для предпринимателей и руководителей"
    item = data["sections"][1]["items"][0]
    assert item == {
        "title": "Новая модель",
        "summary": "что умеет свежий релиз & где он полезен.",
        "link": "https://t.me/yasnovolkova/701",
    }
    assert data["latest_post"]["link"].endswith("/702")
    assert "🎤" not in data["latest_post"]["text"]


def test_greeting_and_full_digest():
    resp = skill.handler(make_event(new=True))
    assert "Ясно Понятно" in resp["response"]["text"]
    assert not resp["response"]["end_session"]

    resp = skill.handler(make_event("что нового"))
    text = resp["response"]["text"]
    assert "Агенты в продажах" in text and "Голосовые ИИ" in text
    assert "И-И" in resp["response"]["tts"]


def test_rubric_and_missing_rubric():
    resp = skill.handler(make_event("расскажи ии тренды"))
    assert "Новая модель" in resp["response"]["text"]
    assert "Агенты в продажах" not in resp["response"]["text"]

    resp = skill.handler(make_event("что для маркетологов"))
    assert "ничего не было" in resp["response"]["text"]


def test_latest_post_and_exit():
    resp = skill.handler(make_event("последний пост"))
    assert "Свежий пост про голос" in resp["response"]["text"]

    resp = skill.handler(make_event("хватит"))
    assert resp["response"]["end_session"]


def test_paging_keeps_state_small():
    pages = skill.chunk(["слово " * 100] * 5)
    assert len(pages) > 1 and all(len(p) <= skill.MAX_CHARS for p in pages)

    # Long digest: 4 rubrics x 6 items with long summaries -> several pages
    long_digest = "\n".join(
        f"{emoji} <b>Рубрика {n}</b>\n" + "\n".join(
            f"• <b>Пункт {n}.{i}</b> — " + "очень длинное описание поста " * 6 + "."
            for i in range(6)
        )
        for n, emoji in enumerate(["💼", "🛠", "🧠", "☕"])
    )
    saved = skill._cache["data"]
    skill._cache["data"] = build_alice_data(long_digest, POSTS)
    try:
        resp = skill.handler(make_event("что нового"))
        seen = [resp["response"]["text"]]
        while "Сказать дальше?" in resp["response"]["text"]:
            state = resp["session_state"]
            assert len(json.dumps(state, ensure_ascii=False).encode()) < 1024
            resp = skill.handler(make_event("дальше", state=state))
            seen.append(resp["response"]["text"])
            assert len(resp["response"]["text"]) <= 1024
        assert len(seen) > 2
        assert "Пункт 3.5" in seen[-1]

        repeat = skill.handler(make_event("повтори", state={"mode": "full", "page": 1}))
        assert repeat["response"]["text"] == seen[1]

        done = skill.handler(make_event("дальше", state={"mode": "full", "page": len(seen) - 1}))
        assert "Это всё" in done["response"]["text"]
    finally:
        skill._cache["data"] = saved


def test_no_data():
    saved = skill._cache["data"]
    skill._cache["data"] = None
    try:
        resp = skill.handler(make_event(new=True))
        assert "не готов" in resp["response"]["text"]
    finally:
        skill._cache["data"] = saved
