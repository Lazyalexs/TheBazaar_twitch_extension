from __future__ import annotations

import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, load_settings
from .logging_setup import configure_logging
from .protocol import PubSubEnvelope, compact_size_bytes
from .rate_limit import InMemoryRateLimiter
from .security import JwtError, extract_bearer_token, require_role, verify_hs256_jwt
from .twitch import TwitchPubSubClient


settings: Settings = load_settings()
configure_logging(settings.env)
logger = logging.getLogger("ebs")

rate_limiter = InMemoryRateLimiter(settings.min_send_interval_seconds)
twitch_client = TwitchPubSubClient(settings)
latest_by_channel: dict[str, dict[str, Any]] = {}
last_seen_by_channel: dict[str, tuple[str, int]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await twitch_client.aclose()

app = FastAPI(
    title="The Bazaar Twitch EBS",
    version="0.1.0",
    docs_url="/docs" if settings.env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Bazaar-Companion-Token"],
)


def _expected_companion_token(channel_id: str) -> str | None:
    return settings.companion_tokens.get(channel_id)


def _require_companion_auth(
    *,
    channel_id: str,
    authorization: str | None,
    x_bazaar_companion_token: str | None,
) -> None:
    provided = extract_bearer_token(authorization) or x_bazaar_companion_token
    expected = _expected_companion_token(channel_id)
    if not expected:
        logger.warning(
            "auth_failed_companion",
            extra={
                "channel_id": channel_id,
                "has_authorization": bool(provided),
                "reason": "channel_not_configured",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "channel_not_configured"},
        )
    if not provided or not hmac.compare_digest(provided, expected):
        logger.warning(
            "auth_failed_companion",
            extra={
                "channel_id": channel_id,
                "has_authorization": bool(provided),
                "reason": "invalid_token",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_companion_token"},
        )


def _authenticate_channel_reader(
    *,
    channel_id: str,
    authorization: str | None,
    x_bazaar_companion_token: str | None,
) -> None:
    """Authenticate a channel read request in production. No-op in development."""
    if settings.env != "production":
        return

    bearer = extract_bearer_token(authorization)
    companion_provided = bearer or x_bazaar_companion_token

    # Try Twitch JWT first.
    if bearer and settings.twitch_secret_base64:
        try:
            payload = verify_hs256_jwt(bearer, settings.twitch_secret_base64)
            require_role(payload, {"broadcaster", "moderator"})
            return
        except (JwtError, HTTPException):
            pass  # JWT failed; fall through to companion token.

    # Try companion token.
    expected = _expected_companion_token(channel_id)
    if expected and companion_provided and hmac.compare_digest(companion_provided, expected):
        return

    if not authorization and not x_bazaar_companion_token:
        logger.warning(
            "auth_failed_reader",
            extra={"channel_id": channel_id, "reason": "missing_auth"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"error": "missing_auth"})
    logger.warning(
        "auth_failed_reader",
        extra={"channel_id": channel_id, "reason": "invalid_auth"},
    )
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"error": "invalid_auth"})


@app.get("/health")
def health() -> dict[str, Any]:
    if settings.env == "production":
        return {"ok": True}
    return {
        "ok": True,
        "env": settings.env,
        "dryRun": settings.dry_run,
        "publicUrl": settings.public_url,
        "twitchConfigured": settings.twitch_configured,
        "configuredChannels": sorted(settings.companion_tokens.keys()),
        "limits": {
            "maxPayloadBytes": settings.max_payload_bytes,
            "minSendIntervalSeconds": settings.min_send_interval_seconds,
        },
    }


@app.post("/v1/companion/{channel_id}/snapshot")
async def ingest_companion_snapshot(
    channel_id: str,
    envelope: PubSubEnvelope,
    request: Request,
    authorization: str | None = Header(default=None),
    x_bazaar_companion_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_companion_auth(
        channel_id=channel_id,
        authorization=authorization,
        x_bazaar_companion_token=x_bazaar_companion_token,
    )

    message = envelope.model_dump(exclude_none=True)
    size_bytes = compact_size_bytes(message)
    if size_bytes > settings.max_payload_bytes:
        logger.warning(
            "payload_too_large",
            extra={
                "channel_id": channel_id,
                "size_bytes": size_bytes,
                "max_payload_bytes": settings.max_payload_bytes,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "payload_too_large",
                "sizeBytes": size_bytes,
                "maxPayloadBytes": settings.max_payload_bytes,
            },
        )

    run_id = envelope.runId
    seq = envelope.seq
    last_entry = last_seen_by_channel.get(channel_id)
    if last_entry is not None:
        last_run_id, last_seq = last_entry
        if last_run_id == run_id and seq <= last_seq:
            logger.warning(
                "dedup_hit",
                extra={
                    "channel_id": channel_id,
                    "run_id": run_id,
                    "seq": seq,
                },
            )
            return {
                "ok": True,
                "dedup": True,
                "channelId": channel_id,
                "seq": seq,
            }

    allowed, retry_after = rate_limiter.allow(channel_id)
    if not allowed:
        logger.warning(
            "rate_limited",
            extra={
                "channel_id": channel_id,
                "retry_after_seconds": round(retry_after, 3),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "retryAfterSeconds": round(retry_after, 3),
            },
        )

    latest_by_channel[channel_id] = {
        "receivedAt": int(time.time() * 1000),
        "sizeBytes": size_bytes,
        "remote": request.client.host if request.client else None,
        "message": message,
    }

    last_seen_by_channel[channel_id] = (run_id, seq)
    if settings.dry_run or not settings.twitch_configured:
        return {
            "ok": True,
            "dryRun": True,
            "sentToTwitch": False,
            "channelId": channel_id,
            "sizeBytes": size_bytes,
            "seq": envelope.seq,
        }

    result = await twitch_client.send_broadcast(channel_id=channel_id, message=message)
    if result.status_code >= 400:
        extra_ctx: dict[str, Any] = {
            "channel_id": channel_id,
            "status_code": result.status_code,
        }
        if result.status_code < 500:
            extra_ctx["body"] = result.body
        logger.warning("twitch_pubsub_failed", extra=extra_ctx)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "twitch_pubsub_failed",
                "statusCode": result.status_code,
                "body": result.body,
            },
        )

    logger.info(
        "snapshot_ingested",
        extra={
            "channel_id": channel_id,
            "seq": seq,
            "size_bytes": size_bytes,
            "sent_to_twitch": True,
        },
    )
    return {
        "ok": True,
        "dryRun": False,
        "sentToTwitch": True,
        "channelId": channel_id,
        "sizeBytes": size_bytes,
        "seq": envelope.seq,
        "twitchStatusCode": result.status_code,
    }


@app.get("/v1/channels/{channel_id}/latest")
def get_latest_channel_state(
    channel_id: str,
    authorization: str | None = Header(default=None),
    x_bazaar_companion_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authenticate_channel_reader(
        channel_id=channel_id,
        authorization=authorization,
        x_bazaar_companion_token=x_bazaar_companion_token,
    )

    latest = latest_by_channel.get(channel_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_state"},
        )

    return {k: v for k, v in latest.items() if k != "remote"}


@app.post("/v1/extension/setup")
def extension_setup(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_twitch_jwt"},
        )
    if not settings.twitch_secret_base64:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "twitch_secret_not_configured"},
        )

    try:
        payload = verify_hs256_jwt(token, settings.twitch_secret_base64)
    except JwtError as exc:
        logger.warning(
            "jwt_invalid_setup",
            extra={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_twitch_jwt", "detail": str(exc)},
        ) from exc

    try:
        require_role(payload, {"broadcaster", "moderator"})
    except JwtError:
        logger.warning(
            "forbidden_role",
            extra={"role": payload.get("role")},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden_role"},
        ) from None

    return {
        "ok": True,
        "channelId": payload.get("channel_id"),
        "role": payload.get("role"),
        "extensionVersion": settings.twitch_extension_version,
    }
