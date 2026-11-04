import os
import sys
import types
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yc_handler  # noqa: E402

TIMER_EVENT = {"messages": [{"event_metadata": {
    "event_type": "yandex.cloud.events.serverless.triggers.TimerMessage"}}]}


def ctx():
    return types.SimpleNamespace(token={"access_token": "iam-token"})


def test_routes_timer_to_weekly_job():
    fake_main = types.SimpleNamespace(run_digest=mock.Mock(return_value={"sections": []}))
    with mock.patch.dict(os.environ, {"DIGEST_BUCKET": "b", "IS_TEST": "true"}), \
            mock.patch.dict(sys.modules, {"main": fake_main}), \
            mock.patch.object(yc_handler, "save_digest") as save:
        resp = yc_handler.handler(TIMER_EVENT, ctx())
    fake_main.run_digest.assert_called_once_with(days=7, is_test=True, save_local=False)
    save.assert_called_once_with({"sections": []}, "iam-token")
    assert resp["statusCode"] == 200


def test_no_posts_skips_save():
    fake_main = types.SimpleNamespace(run_digest=mock.Mock(return_value=None))
    with mock.patch.dict(os.environ, {"DIGEST_BUCKET": "b"}), \
            mock.patch.dict(sys.modules, {"main": fake_main}), \
            mock.patch.object(yc_handler, "save_digest") as save:
        resp = yc_handler.handler(TIMER_EVENT, ctx())
    save.assert_not_called()
    assert resp["body"] == "no posts"


def test_routes_alice_and_passes_storage_token():
    alice = yc_handler.alice
    event = {"request": {"command": "что нового", "nlu": {"tokens": ["что", "нового"]}},
             "session": {"new": False}, "state": {"session": {}}, "version": "1.0"}
    captured = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"intro": "", "sections": [{"key": "ai", "title": "T", "items": [{"title": "X", "summary": "Y"}]}]}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["token"] = req.headers.get("X-yacloud-subjecttoken")
        return Resp()

    saved = dict(alice._cache)
    alice._cache.update(data=None, ts=0.0)
    env = {k: v for k, v in os.environ.items() if k != "DIGEST_URL"}
    env["DIGEST_BUCKET"] = "yasno"
    try:
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(alice.urllib.request, "urlopen", fake_urlopen):
            resp = yc_handler.handler(event, ctx())
    finally:
        alice._cache.update(saved)
    assert captured == {"url": "https://storage.yandexcloud.net/yasno/digest.json", "token": "iam-token"}
    assert "X: Y." in resp["response"]["text"]
