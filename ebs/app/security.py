from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class JwtError(ValueError):
    pass


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def decode_extension_secret(secret_base64: str) -> bytes:
    if not secret_base64:
        raise JwtError("Missing Twitch extension secret")
    try:
        return base64.b64decode(secret_base64, validate=True)
    except Exception as exc:
        raise JwtError("Invalid base64 Twitch extension secret") from exc


def sign_hs256_jwt(payload: dict[str, Any], secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(signature)}"


def sign_twitch_ebs_jwt(
    *,
    secret_base64: str,
    owner_id: str,
    channel_id: str,
    ttl_seconds: int,
) -> str:
    now = int(time.time())
    payload = {
        "exp": now + ttl_seconds,
        "user_id": owner_id,
        "role": "external",
        "channel_id": channel_id,
        "pubsub_perms": {"send": ["broadcast"]},
    }
    return sign_hs256_jwt(payload, decode_extension_secret(secret_base64))


def verify_hs256_jwt(token: str, secret_base64: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise JwtError("Malformed JWT") from exc

    secret = decode_extension_secret(secret_base64)
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, actual):
        raise JwtError("Invalid JWT signature")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        raise JwtError("Invalid JWT payload") from exc

    exp = payload.get("exp")
    if exp is not None and int(exp) < int(time.time()):
        raise JwtError("Expired JWT")

    return payload


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip()

