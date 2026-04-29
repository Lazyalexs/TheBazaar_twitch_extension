from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env_files() -> None:
    explicit = os.environ.get("EBS_ENV_FILE")
    candidates = []
    if explicit:
        candidates.append(Path(explicit))

    cwd = Path.cwd()
    candidates.extend([cwd / ".env", cwd.parent / ".env"])

    for path in candidates:
        _load_env_file(path)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _load_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Expected JSON object")
    return loaded


@dataclass(frozen=True)
class Settings:
    env: str
    public_url: str
    dry_run: bool
    twitch_client_id: str
    twitch_owner_id: str
    twitch_secret_base64: str
    twitch_extension_version: str
    twitch_pubsub_url: str
    jwt_ttl_seconds: int
    max_payload_bytes: int
    min_send_interval_seconds: float
    companion_tokens: dict[str, str]
    cors_origins: list[str]

    @property
    def twitch_configured(self) -> bool:
        return bool(
            self.twitch_client_id
            and self.twitch_owner_id
            and self.twitch_secret_base64
        )


def load_settings() -> Settings:
    load_env_files()

    companion_tokens = {
        str(channel_id): str(token)
        for channel_id, token in _load_json_dict(
            os.environ.get("COMPANION_TOKENS_JSON")
        ).items()
    }

    default_channel = os.environ.get("COMPANION_CHANNEL_ID", "dev-channel")
    default_token = os.environ.get("COMPANION_SHARED_TOKEN", "dev-companion-token")
    if default_channel and default_token:
        companion_tokens.setdefault(default_channel, default_token)

    cors_origins_raw = os.environ.get("EBS_CORS_ORIGINS", "*")
    cors_origins = [
        origin.strip()
        for origin in cors_origins_raw.split(",")
        if origin.strip()
    ]

    return Settings(
        env=os.environ.get("EBS_ENV", "development"),
        public_url=os.environ.get("EBS_PUBLIC_URL", "http://127.0.0.1:8000"),
        dry_run=_as_bool(os.environ.get("EBS_DRY_RUN"), default=True),
        twitch_client_id=os.environ.get("TWITCH_EXTENSION_CLIENT_ID", ""),
        twitch_owner_id=os.environ.get("TWITCH_EXTENSION_OWNER_ID", ""),
        twitch_secret_base64=os.environ.get("TWITCH_EXTENSION_SECRET_BASE64", ""),
        twitch_extension_version=os.environ.get("TWITCH_EXTENSION_VERSION", "0.0.1"),
        twitch_pubsub_url=os.environ.get(
            "TWITCH_PUBSUB_URL",
            "https://api.twitch.tv/helix/extensions/pubsub",
        ),
        jwt_ttl_seconds=_as_int(os.environ.get("EBS_JWT_TTL_SECONDS"), 120),
        max_payload_bytes=_as_int(os.environ.get("EBS_MAX_PAYLOAD_BYTES"), 5000),
        min_send_interval_seconds=_as_float(
            os.environ.get("EBS_MIN_SEND_INTERVAL_SECONDS"),
            1.0,
        ),
        companion_tokens=companion_tokens,
        cors_origins=cors_origins,
    )

