import os
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import publisher  # noqa: E402
import scraper  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402


# ---------- publisher ----------

def test_short_message_not_split():
    assert publisher.split_message("<b>Привет</b>") == ["<b>Привет</b>"]


def test_long_message_split_on_blocks_and_keeps_tags():
    block = "\n".join(f"• <b>Пункт {i}</b> — описание. <a href=\"https://t.me/x/{i}\">Читать пост</a>"
                      for i in range(20))
    text = "\n\n".join([block] * 5)
    parts = publisher.split_message(text)
    assert len(parts) > 1
    assert all(len(p) <= publisher.TG_MAX_LENGTH for p in parts)
    for p in parts:
        assert p.count("<b>") == p.count("</b>")
        assert p.count("<a ") == p.count("</a>")
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_publish_sends_every_part():
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

    with mock.patch.dict(os.environ, {"TG_BOT_TOKEN": "t", "TG_TEST_CHANNEL_ID": "@test"}), \
            mock.patch.object(publisher.requests, "post",
                              side_effect=lambda url, json, timeout: calls.append(json) or Resp()):
        assert publisher.publish_to_telegram("абв\n\n" * 3000, is_test=True)
    assert len(calls) > 1 and all(c["chat_id"] == "@test" for c in calls)


# ---------- scraper ----------

def _page(posts):
    html = ""
    for post_id, when in posts:
        html += f"""
        <div class="tgme_widget_message" data-post="chan/{post_id}">
          <div class="tgme_widget_message_text">Текст поста номер {post_id}, достаточно длинный.</div>
          <a class="tgme_widget_message_date" href="https://t.me/chan/{post_id}">
            <time class="time" datetime="{when.isoformat()}"></time></a>
        </div>"""
    return BeautifulSoup(html, "html.parser").find_all("div", class_="tgme_widget_message")


def test_scraper_paginates_until_cutoff():
    now = datetime.now(timezone.utc)
    pages = {
        None: _page([(30 + i, now - timedelta(hours=i)) for i in range(20)]),
        30: _page([(10 + i, now - timedelta(days=3, hours=i)) for i in range(20)]),
        10: _page([(i, now - timedelta(days=10 + i)) for i in range(1, 10)]),
    }
    requested = []

    def fake_fetch(self, before=None):
        requested.append(before)
        return pages[before]

    with mock.patch.object(scraper.TelegramScraper, "_fetch_page", fake_fetch):
        posts = scraper.TelegramScraper("@chan").get_recent_posts(days=7)

    assert requested == [None, 30, 10]
    assert len(posts) == 40
    assert posts == sorted(posts, key=lambda p: p["date"])
    assert posts[-1]["link"] == "https://t.me/chan/30"


def test_scraper_stops_on_first_page_when_old_enough():
    now = datetime.now(timezone.utc)
    page = _page([(5, now - timedelta(days=1)), (4, now - timedelta(days=9))])
    with mock.patch.object(scraper.TelegramScraper, "_fetch_page", return_value=page) as fetch:
        posts = scraper.TelegramScraper("chan").get_recent_posts(days=7)
    assert fetch.call_count == 1
    assert [p["link"] for p in posts] == ["https://t.me/chan/5"]
