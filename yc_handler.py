"""Single Yandex Cloud Function for the whole project.

Entry point: `yc_handler.handler`.

* Timer trigger (every Sunday) -> scrape, generate, publish to Telegram and
  save the voice version to Object Storage (`<DIGEST_BUCKET>/digest.json`).
* Alice request -> answer with the skill in alice_skill/index.py, which reads
  that same JSON.

Environment variables: GEMINI_API_KEY, TG_BOT_TOKEN, TG_CHANNEL_ID,
TG_TEST_CHANNEL_ID, DIGEST_BUCKET, optional IS_TEST / DIGEST_DAYS / GEMINI_MODEL.
The function's service account needs storage.editor and functions.functionInvoker.
"""
import json
import os
import urllib.request

from alice_skill import index as alice

STORAGE_URL = "https://storage.yandexcloud.net"


def digest_url():
    return f"{STORAGE_URL}/{os.environ['DIGEST_BUCKET']}/digest.json"


def is_timer_event(event):
    messages = (event or {}).get("messages") or []
    return bool(messages) and str(
        messages[0].get("event_metadata", {}).get("event_type", "")
    ).endswith("TimerMessage")


def save_digest(data, token):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    req = urllib.request.Request(
        digest_url(),
        data=body,
        method="PUT",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-YaCloud-SubjectToken": token or "",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Digest saved to {digest_url()} (HTTP {resp.status})")


def run_weekly_job(context):
    # Heavy imports only for the weekly job, so Alice replies stay fast
    from main import run_digest

    days = int(os.environ.get("DIGEST_DAYS") or 7)
    is_test = os.environ.get("IS_TEST", "false").lower() == "true"
    alice_data = run_digest(days=days, is_test=is_test, save_local=False)
    if alice_data:
        save_digest(alice_data, alice.context_token(context))
    return {"statusCode": 200, "body": "no posts" if alice_data is None else "ok"}


def handler(event, context=None):
    if is_timer_event(event):
        return run_weekly_job(context)
    os.environ.setdefault("DIGEST_URL", digest_url())
    return alice.handler(event, context)
