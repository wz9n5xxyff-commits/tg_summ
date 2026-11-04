"""Uploads the Alice digest to a private Yandex Object Storage bucket.

Used when the weekly job runs outside Yandex Cloud (Telegram and Gemini are not
reachable from Yandex Cloud regions). Authenticates with an authorized key of a
service account (YC_SA_KEY, JSON) -> JWT PS256 -> IAM token.
"""
import json
import os
import time

import requests

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
STORAGE_URL = "https://storage.yandexcloud.net"


def iam_token(sa_key_json):
    import jwt  # PyJWT[crypto]

    key = json.loads(sa_key_json)
    now = int(time.time())
    encoded = jwt.encode(
        {"aud": IAM_URL, "iss": key["service_account_id"], "iat": now, "exp": now + 3600},
        key["private_key"],
        algorithm="PS256",
        headers={"kid": key["id"]},
    )
    resp = requests.post(IAM_URL, json={"jwt": encoded}, timeout=30)
    resp.raise_for_status()
    return resp.json()["iamToken"]


def upload_digest(data, bucket=None, sa_key_json=None):
    bucket = bucket or os.environ["DIGEST_BUCKET"]
    token = iam_token(sa_key_json or os.environ["YC_SA_KEY"])
    url = f"{STORAGE_URL}/{bucket}/digest.json"
    resp = requests.put(
        url,
        data=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", "X-YaCloud-SubjectToken": token},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"Digest uploaded to {url} (HTTP {resp.status_code})")
