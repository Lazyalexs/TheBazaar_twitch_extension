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
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"COMPANION_TOKENS_JSON is not valid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("COMPANION_TOKENS_JSON must be a JSON object")
    return loaded


@dataclass(frozen=True)
class Settings:
    env: str
    public_url: str
    api_url: str
    dry_run: bool
    twitch_client_id: str
    twitch_owner_id: str
    twitch_secret_base64: str
    twitch_extension_version: str
    twitch_pubsub_url: str
    twitch_gql_client_id: str
    jwt_ttl_seconds: int
    max_payload_bytes: int
    min_send_interval_seconds: float
    companion_tokens: dict[str, str]
    cors_origins: list[str]
    cors_origin_regex: str | None
    database_path: Path
    mail_provider: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_starttls: bool
    smtp_ssl: bool
    yandex_postbox_endpoint: str
    yandex_postbox_from: str
    yandex_postbox_iam_token: str
    yandex_postbox_access_key_id: str
    yandex_postbox_secret_access_key: str
    yandex_postbox_region: str

    @property
    def twitch_configured(self) -> bool:
        return bool(
            self.twitch_client_id
            and self.twitch_owner_id
            and self.twitch_secret_base64
        )

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def yandex_postbox_configured(self) -> bool:
        return bool(
            self.yandex_postbox_from
            and (
                self.yandex_postbox_iam_token
                or (
                    self.yandex_postbox_access_key_id
                    and self.yandex_postbox_secret_access_key
                )
            )
        )

    @property
    def mail_configured(self) -> bool:
        if self.mail_provider == "yandex_postbox":
            return self.yandex_postbox_configured
        return self.smtp_configured


def load_settings() -> Settings:
    load_env_files()
    public_url = os.environ.get("EBS_PUBLIC_URL", "http://127.0.0.1:8000")

    ebs_env = os.environ.get("EBS_ENV", "development")
    is_production = ebs_env == "production"

    companion_tokens = {
        str(channel_id): str(token)
        for channel_id, token in _load_json_dict(
            os.environ.get("COMPANION_TOKENS_JSON")
        ).items()
    }

    if is_production:
        default_channel = os.environ.get("COMPANION_CHANNEL_ID", "")
        default_token = os.environ.get("COMPANION_SHARED_TOKEN", "")
    else:
        default_channel = os.environ.get("COMPANION_CHANNEL_ID", "dev-channel")
        default_token = os.environ.get("COMPANION_SHARED_TOKEN", "dev-companion-token")

    if default_channel and default_token:
        companion_tokens.setdefault(default_channel, default_token)

    if is_production:
        for channel_id, token in companion_tokens.items():
            if len(token) < 32:
                raise RuntimeError(
                    f'Companion token for channel "{channel_id}" is too short: '
                    f"minimum 32 chars"
                )

    if is_production:
        cors_origins_raw = os.environ.get("EBS_CORS_ORIGINS")
        if not cors_origins_raw:
            raise RuntimeError(
                "EBS_CORS_ORIGINS must be set explicitly in production"
            )
    else:
        cors_origins_raw = os.environ.get("EBS_CORS_ORIGINS", "*")

    cors_origins = [
        origin.strip()
        for origin in cors_origins_raw.split(",")
        if origin.strip()
    ]

    cors_origin_regex_raw = os.environ.get("EBS_CORS_ORIGIN_REGEX", "")
    if cors_origin_regex_raw:
        cors_origin_regex = cors_origin_regex_raw
    elif is_production:
        cors_origin_regex = r"^https://[a-z0-9-]+\.ext-twitch\.tv$"
    else:
        cors_origin_regex = None

    return Settings(
        env=ebs_env,
        public_url=public_url,
        api_url=os.environ.get("EBS_API_URL", public_url),
        dry_run=_as_bool(os.environ.get("EBS_DRY_RUN"), default=True),
        twitch_client_id=os.environ.get("TWITCH_EXTENSION_CLIENT_ID", ""),
        twitch_owner_id=os.environ.get("TWITCH_EXTENSION_OWNER_ID", ""),
        twitch_secret_base64=os.environ.get("TWITCH_EXTENSION_SECRET_BASE64", ""),
        twitch_extension_version=os.environ.get("TWITCH_EXTENSION_VERSION", "0.0.1"),
        twitch_pubsub_url=os.environ.get(
            "TWITCH_PUBSUB_URL",
            "https://api.twitch.tv/helix/extensions/pubsub",
        ),
        twitch_gql_client_id=os.environ.get(
            "EBS_TWITCH_GQL_CLIENT_ID",
            "kimne78kx3ncx6brgo4mv6wki5h1ko",
        ),
        jwt_ttl_seconds=_as_int(os.environ.get("EBS_JWT_TTL_SECONDS"), 120),
        max_payload_bytes=_as_int(os.environ.get("EBS_MAX_PAYLOAD_BYTES"), 5000),
        min_send_interval_seconds=_as_float(
            os.environ.get("EBS_MIN_SEND_INTERVAL_SECONDS"),
            1.0,
        ),
        companion_tokens=companion_tokens,
        cors_origins=cors_origins,
        cors_origin_regex=cors_origin_regex,
        database_path=Path(os.environ.get("EBS_DATABASE_PATH", "data/ebs.sqlite3")),
        mail_provider=os.environ.get("EBS_MAIL_PROVIDER", "smtp").strip().lower(),
        smtp_host=os.environ.get("EBS_SMTP_HOST", ""),
        smtp_port=_as_int(os.environ.get("EBS_SMTP_PORT"), 587),
        smtp_username=os.environ.get("EBS_SMTP_USERNAME", ""),
        smtp_password=os.environ.get("EBS_SMTP_PASSWORD", ""),
        smtp_from=os.environ.get("EBS_SMTP_FROM", ""),
        smtp_starttls=_as_bool(os.environ.get("EBS_SMTP_STARTTLS"), default=True),
        smtp_ssl=_as_bool(os.environ.get("EBS_SMTP_SSL"), default=False),
        yandex_postbox_endpoint=os.environ.get(
            "EBS_YANDEX_POSTBOX_ENDPOINT",
            "https://postbox.cloud.yandex.net/v2/email/outbound-emails",
        ),
        yandex_postbox_from=os.environ.get("EBS_YANDEX_POSTBOX_FROM", ""),
        yandex_postbox_iam_token=os.environ.get("EBS_YANDEX_POSTBOX_IAM_TOKEN", ""),
        yandex_postbox_access_key_id=os.environ.get(
            "EBS_YANDEX_POSTBOX_ACCESS_KEY_ID",
            "",
        ),
        yandex_postbox_secret_access_key=os.environ.get(
            "EBS_YANDEX_POSTBOX_SECRET_ACCESS_KEY",
            "",
        ),
        yandex_postbox_region=os.environ.get(
            "EBS_YANDEX_POSTBOX_REGION",
            "ru-central1",
        ),
    )
