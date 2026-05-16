from __future__ import annotations

import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, load_settings
from .database import StreamerRecord, TokenStore, normalize_channel_id
from .logging_setup import configure_logging
from .mailer import EmailSender, RegistrationCredentials
from .protocol import PubSubEnvelope, compact_size_bytes
from .rate_limit import InMemoryRateLimiter
from .security import JwtError, extract_bearer_token, require_role, verify_hs256_jwt
from .site import render_landing_page, render_registration_page, supported_language
from .twitch import TwitchPubSubClient
from .twitch_identity import TwitchIdentityResolver


settings: Settings = load_settings()
configure_logging(settings.env)
logger = logging.getLogger("ebs")

rate_limiter = InMemoryRateLimiter(settings.min_send_interval_seconds)
twitch_client = TwitchPubSubClient(settings)
identity_resolver = TwitchIdentityResolver(settings.twitch_gql_client_id)
token_store = TokenStore(settings.database_path)
email_sender = EmailSender(settings)
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


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel_login: str | None = Field(default=None, alias="channelLogin", max_length=120)
    channel_id: str | None = Field(default=None, alias="channelId", max_length=32)
    email: str = Field(min_length=3, max_length=254)
    display_name: str | None = Field(default="", alias="displayName", max_length=80)
    language: str = Field(default="ru", max_length=8)


class VerifyCompanionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel_login: str | None = Field(default=None, alias="channelLogin", max_length=120)
    channel_id: str | None = Field(default=None, alias="channelId", max_length=32)
    token: str = Field(min_length=1, max_length=300)

    def identifier(self) -> str:
        return (self.channel_login or self.channel_id or "").strip()


def _expected_companion_token(channel_id: str) -> str | None:
    return settings.companion_tokens.get(channel_id)


def _companion_token_is_valid(identifier: str, provided: str | None) -> bool:
    if not provided:
        return False
    if token_store.verify_token(identifier, provided):
        return True

    expected = _expected_companion_token(identifier)
    return bool(expected and hmac.compare_digest(provided, expected))


def _require_companion_auth(
    *,
    identifier: str,
    authorization: str | None,
    x_bazaar_companion_token: str | None,
) -> StreamerRecord | None:
    provided = extract_bearer_token(authorization) or x_bazaar_companion_token
    if _companion_token_is_valid(identifier, provided):
        return token_store.get_streamer(identifier)

    reason = (
        "channel_not_configured"
        if not token_store.get_streamer(identifier) and not _expected_companion_token(identifier)
        else "invalid_token"
    )
    logger.warning(
        "auth_failed_companion",
        extra={
            "identifier": identifier,
            "has_authorization": bool(provided),
            "reason": reason,
        },
    )
    # P1-5: always 401, don't leak channel configuration via 403
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "invalid_companion_token"},
    )


def _is_numeric_channel_id(value: str) -> bool:
    try:
        normalize_channel_id(value)
    except ValueError:
        return False
    return True


def _latest_keys(identifier: str, streamer: StreamerRecord | None) -> set[str]:
    keys = {identifier}
    if streamer:
        keys.add(streamer.channel_id)
        keys.add(streamer.streamer_key)
        if streamer.channel_login:
            keys.add(streamer.channel_login)
    return {key for key in keys if key}


@app.head("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/", response_class=HTMLResponse)
def landing(lang: str = "ru") -> HTMLResponse:
    return HTMLResponse(
        render_landing_page(
            language=supported_language(lang),
            public_url=settings.public_url,
        )
    )


@app.head("/new", response_class=HTMLResponse, include_in_schema=False)
@app.get("/new", response_class=HTMLResponse)
def new_page(lang: str = "ru") -> HTMLResponse:
    return landing(lang=lang)


@app.head("/register", response_class=HTMLResponse, include_in_schema=False)
@app.get("/register", response_class=HTMLResponse)
def register_page(lang: str = "ru") -> HTMLResponse:
    return HTMLResponse(
        render_registration_page(
            language=supported_language(lang),
            public_url=settings.public_url,
            api_url=settings.api_url,
        )
    )


@app.post("/api/register")
def register_streamer(request: RegisterRequest) -> dict[str, Any]:
    try:
        channel_login = ""
        channel_id = request.channel_id or ""
        display_name = request.display_name
        if request.channel_login:
            identity = identity_resolver.resolve_login(request.channel_login)
            channel_login = identity.login
            channel_id = identity.channel_id
            display_name = display_name or identity.display_name
        result = token_store.register_streamer(
            channel_id=channel_id,
            channel_login=channel_login,
            email=request.email,
            display_name=display_name,
            language=request.language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc)},
        ) from exc

    email_sent = False
    email_error = ""
    try:
        email_sent = email_sender.send_registration(
            RegistrationCredentials(
                recipient=result.streamer.email,
                channel_id=result.streamer.channel_id,
                channel_login=result.streamer.channel_login,
                companion_token=result.token,
                display_name=result.streamer.display_name,
                language=result.streamer.language,
                public_url=settings.public_url.rstrip("/"),
            )
        )
    except Exception:
        email_error = "smtp_failed"

    response = {
        "ok": True,
        "created": result.created,
        "channelId": result.streamer.channel_id,
        "channelLogin": result.streamer.channel_login,
        "email": result.streamer.email,
        "displayName": result.streamer.display_name,
        "language": result.streamer.language,
        "companionToken": result.token,
        "emailSent": email_sent,
    }
    if email_error:
        response["emailError"] = email_error
    return response


@app.post("/api/companion/verify")
def verify_companion(request: VerifyCompanionRequest) -> dict[str, Any]:
    identifier = request.identifier()
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "channel_login_required"},
        )
    if not _companion_token_is_valid(identifier, request.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_companion_token"},
        )

    streamer = token_store.get_streamer(identifier)
    return {
        "ok": True,
        "channelId": streamer.channel_id if streamer else identifier,
        "channelLogin": streamer.channel_login if streamer else "",
        "displayName": streamer.display_name if streamer else "",
        "language": streamer.language if streamer else "ru",
    }


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
        "apiUrl": settings.api_url,
        "twitchConfigured": settings.twitch_configured,
        "configuredChannels": sorted(settings.companion_tokens.keys()),
        "databasePath": str(settings.database_path),
        "registrationInviteRequired": False,
        "smtpConfigured": settings.smtp_configured,
        "mailProvider": settings.mail_provider,
        "mailConfigured": settings.mail_configured,
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
    streamer = _require_companion_auth(
        identifier=channel_id,
        authorization=authorization,
        x_bazaar_companion_token=x_bazaar_companion_token,
    )
    twitch_channel_id = streamer.channel_id if streamer else channel_id

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
    last_entry = last_seen_by_channel.get(twitch_channel_id)
    if last_entry is not None:
        last_run_id, last_seq = last_entry
        if last_run_id == run_id and seq <= last_seq:
            logger.warning(
                "dedup_hit",
                extra={
                    "channel_id": twitch_channel_id,
                    "run_id": run_id,
                    "seq": seq,
                },
            )
            return {
                "ok": True,
                "dedup": True,
                "channelId": twitch_channel_id,
                "seq": seq,
            }

    allowed, retry_after = rate_limiter.allow(twitch_channel_id)
    if not allowed:
        logger.warning(
            "rate_limited",
            extra={
                "channel_id": twitch_channel_id,
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

    latest = {
        "receivedAt": int(time.time() * 1000),
        "sizeBytes": size_bytes,
        "remote": request.client.host if request.client else None,
        "message": message,
    }
    for key in _latest_keys(channel_id, streamer):
        latest_by_channel[key] = latest

    last_seen_by_channel[twitch_channel_id] = (run_id, seq)
    if settings.dry_run or not settings.twitch_configured:
        return {
            "ok": True,
            "dryRun": True,
            "sentToTwitch": False,
            "channelId": twitch_channel_id,
            "channelLogin": streamer.channel_login if streamer else "",
            "sizeBytes": size_bytes,
            "seq": envelope.seq,
        }

    if not _is_numeric_channel_id(twitch_channel_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "twitch_channel_id_unresolved"},
        )

    result = await twitch_client.send_broadcast(channel_id=twitch_channel_id, message=message)
    if result.status_code >= 400:
        extra_ctx: dict[str, Any] = {
            "channel_id": twitch_channel_id,
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
            "channel_id": twitch_channel_id,
            "seq": seq,
            "size_bytes": size_bytes,
            "sent_to_twitch": True,
        },
    )
    return {
        "ok": True,
        "dryRun": False,
        "sentToTwitch": True,
        "channelId": twitch_channel_id,
        "channelLogin": streamer.channel_login if streamer else "",
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
