import base64
import time

from ebs.app.security import sign_hs256_jwt, verify_hs256_jwt


def test_sign_and_verify_hs256_jwt_roundtrip():
    secret = b"test-secret"
    token = sign_hs256_jwt(
        {"exp": int(time.time()) + 60, "channel_id": "123"},
        secret,
    )

    payload = verify_hs256_jwt(token, base64.b64encode(secret).decode("ascii"))

    assert payload["channel_id"] == "123"

