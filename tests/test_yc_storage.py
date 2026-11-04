import json
import os
import sys
from unittest import mock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yc_storage  # noqa: E402


def fake_key():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
    return priv, json.dumps({"id": "kid1", "service_account_id": "sa1", "private_key": pem})


def test_upload_digest_signs_jwt_and_puts_json():
    priv, key_json = fake_key()
    post_resp = mock.Mock(**{"json.return_value": {"iamToken": "t1"}})
    with mock.patch.object(yc_storage.requests, "post", return_value=post_resp) as post, \
            mock.patch.object(yc_storage.requests, "put") as put:
        yc_storage.upload_digest({"intro": "Привет"}, bucket="b", sa_key_json=key_json)

    token = post.call_args.kwargs["json"]["jwt"]
    assert jwt.get_unverified_header(token)["kid"] == "kid1"
    claims = jwt.decode(token, priv.public_key(), algorithms=["PS256"], audience=yc_storage.IAM_URL)
    assert claims["iss"] == "sa1"

    url = put.call_args.args[0]
    assert url == "https://storage.yandexcloud.net/b/digest.json"
    assert put.call_args.kwargs["headers"]["X-YaCloud-SubjectToken"] == "t1"
    assert json.loads(put.call_args.kwargs["data"].decode()) == {"intro": "Привет"}
