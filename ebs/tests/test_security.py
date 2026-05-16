import base64
import hashlib
import hmac as hmac_mod
import json
import time

from ebs.app.security import (
    JwtError,
    _b64url_decode,
    _b64url_encode,
    require_role,
    sign_hs256_jwt,
    verify_hs256_jwt,
)


# ── existing roundtrip (must not break) ──────────────────────────────────────

def test_sign_and_verify_hs256_jwt_roundtrip():
    secret = b"test-secret"
    token = sign_hs256_jwt(
        {"exp": int(time.time()) + 60, "channel_id": "123"},
        secret,
    )

    payload = verify_hs256_jwt(token, base64.b64encode(secret).decode("ascii"))

    assert payload["channel_id"] == "123"


# ── header hardening ─────────────────────────────────────────────────────────

def test_tampered_alg_rejected():
    """Header with alg='none' is rejected even with a valid HMAC signature."""
    secret = b"test-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")
    payload = {"exp": int(time.time()) + 60, "channel_id": "123"}

    bad_header = {"alg": "none", "typ": "JWT"}
    header_part = _b64url_encode(
        json.dumps(bad_header, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac_mod.new(secret, signing_input, hashlib.sha256).digest()
    token = f"{header_part}.{payload_part}.{_b64url_encode(signature)}"

    try:
        verify_hs256_jwt(token, secret_b64)
        assert False, "Should have raised JwtError for alg='none'"
    except JwtError as e:
        assert "algorithm" in str(e).lower()


def test_tampered_typ_rejected():
    """Header with typ='JWE' is rejected."""
    secret = b"test-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")
    payload = {"exp": int(time.time()) + 60, "channel_id": "123"}

    bad_header = {"alg": "HS256", "typ": "JWE"}
    header_part = _b64url_encode(
        json.dumps(bad_header, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac_mod.new(secret, signing_input, hashlib.sha256).digest()
    token = f"{header_part}.{payload_part}.{_b64url_encode(signature)}"

    try:
        verify_hs256_jwt(token, secret_b64)
        assert False, "Should have raised JwtError for typ='JWE'"
    except JwtError as e:
        assert "type" in str(e).lower()


# ── clock-skew tolerance ─────────────────────────────────────────────────────

def test_exp_within_skew_accepted():
    """Token expired by <= 60 s is still accepted (60 s clock-skew window)."""
    secret = b"test-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")
    # expired 30 seconds ago
    payload = {"exp": int(time.time()) - 30, "channel_id": "123"}
    token = sign_hs256_jwt(payload, secret)

    result = verify_hs256_jwt(token, secret_b64)
    assert result["channel_id"] == "123"


def test_exp_older_than_skew_rejected():
    """Token expired by > 60 s is rejected."""
    secret = b"test-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")
    # expired 90 seconds ago
    payload = {"exp": int(time.time()) - 90, "channel_id": "123"}
    token = sign_hs256_jwt(payload, secret)

    try:
        verify_hs256_jwt(token, secret_b64)
        assert False, "Should have raised JwtError for expired token"
    except JwtError as e:
        assert "Expired" in str(e)


# ── require_role ─────────────────────────────────────────────────────────────

def test_require_role_allows_expected_roles():
    """broadcaster and moderator pass the gate."""
    require_role({"role": "broadcaster"}, {"broadcaster", "moderator"})
    require_role({"role": "moderator"}, {"broadcaster", "moderator"})


def test_require_role_rejects_viewer():
    """viewer is not in the allowed set."""
    try:
        require_role({"role": "viewer"}, {"broadcaster", "moderator"})
        assert False, "Should have raised JwtError for viewer role"
    except JwtError as e:
        assert "forbidden_role" in str(e)


def test_require_role_rejects_missing_role():
    """Missing 'role' key is treated as not in allowed set."""
    try:
        require_role({}, {"broadcaster", "moderator"})
        assert False, "Should have raised JwtError for missing role"
    except JwtError as e:
        assert "forbidden_role" in str(e)


def test_require_role_rejects_external():
    """external is not in the allowed set."""
    try:
        require_role({"role": "external"}, {"broadcaster", "moderator"})
        assert False, "Should have raised JwtError for external role"
    except JwtError as e:
        assert "forbidden_role" in str(e)
