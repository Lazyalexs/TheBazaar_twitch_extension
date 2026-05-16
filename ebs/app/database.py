from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


SUPPORTED_LANGUAGES = {"ru", "en"}
_CHANNEL_ID_RE = re.compile(r"\d{2,32}")
_CHANNEL_LOGIN_RE = re.compile(r"[a-z0-9_]{3,25}")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LOGIN_KEY_PREFIX = "login:"


@dataclass(frozen=True)
class StreamerRecord:
    streamer_key: str
    channel_id: str
    channel_login: str
    email: str
    display_name: str
    language: str
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class RegistrationResult:
    streamer: StreamerRecord
    token: str
    created: bool


def now_ms() -> int:
    return int(time.time() * 1000)


def normalize_channel_id(channel_id: str) -> str:
    cleaned = str(channel_id).strip()
    if not _CHANNEL_ID_RE.fullmatch(cleaned):
        raise ValueError("channel_id_must_be_numeric")
    return cleaned


def normalize_channel_login(channel_login: str) -> str:
    cleaned = str(channel_login or "").strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    if "://" in cleaned or cleaned.lower().startswith(("twitch.tv/", "www.twitch.tv/")):
        parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
        cleaned = parsed.path.strip("/").split("/", 1)[0]
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0].strip().lower()
    if not _CHANNEL_LOGIN_RE.fullmatch(cleaned):
        raise ValueError("channel_login_invalid")
    return cleaned


def login_streamer_key(channel_login: str) -> str:
    return f"{_LOGIN_KEY_PREFIX}{normalize_channel_login(channel_login)}"


def normalize_language(language: str | None) -> str:
    cleaned = (language or "ru").strip().lower()
    return cleaned if cleaned in SUPPORTED_LANGUAGES else "ru"


def normalize_email(email: str | None) -> str:
    cleaned = (email or "").strip().lower()
    if not cleaned:
        raise ValueError("email_required")
    if len(cleaned) > 254 or not _EMAIL_RE.fullmatch(cleaned):
        raise ValueError("email_invalid")
    return cleaned


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def row_to_streamer(row: sqlite3.Row) -> StreamerRecord:
    streamer_key = str(row["channel_id"])
    twitch_channel_id = str(row["twitch_channel_id"] or "").strip()
    channel_login = str(row["channel_login"] or "").strip()
    return StreamerRecord(
        streamer_key=streamer_key,
        channel_id=twitch_channel_id or streamer_key,
        channel_login=channel_login,
        email=str(row["email"] or ""),
        display_name=str(row["display_name"] or ""),
        language=normalize_language(str(row["language"] or "ru")),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


class TokenStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        if str(self.path) != ":memory:":
            connection.execute("PRAGMA journal_mode=WAL")
        self._init_schema(connection)
        return connection

    def _init_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS streamers (
                channel_id TEXT PRIMARY KEY,
                email TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'ru',
                token_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(streamers)").fetchall()
        }
        if "email" not in columns:
            connection.execute(
                "ALTER TABLE streamers ADD COLUMN email TEXT NOT NULL DEFAULT ''"
            )
        if "channel_login" not in columns:
            connection.execute(
                "ALTER TABLE streamers ADD COLUMN channel_login TEXT NOT NULL DEFAULT ''"
            )
        if "twitch_channel_id" not in columns:
            connection.execute(
                "ALTER TABLE streamers ADD COLUMN twitch_channel_id TEXT NOT NULL DEFAULT ''"
            )
        connection.commit()

    def _lookup_values(self, identifier: str) -> tuple[str, str, str]:
        raw = str(identifier or "").strip()
        channel_login = ""
        twitch_channel_id = ""
        try:
            channel_login = normalize_channel_login(raw)
        except ValueError:
            pass
        try:
            twitch_channel_id = normalize_channel_id(raw)
        except ValueError:
            pass
        streamer_key = login_streamer_key(channel_login) if channel_login else raw
        return raw, streamer_key, twitch_channel_id

    def get_streamer(self, channel_id: str) -> StreamerRecord | None:
        raw, streamer_key, twitch_channel_id = self._lookup_values(channel_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    channel_id,
                    channel_login,
                    twitch_channel_id,
                    email,
                    display_name,
                    language,
                    created_at,
                    updated_at
                FROM streamers
                WHERE channel_id = ?
                   OR channel_id = ?
                   OR channel_login = ?
                   OR twitch_channel_id = ?
                LIMIT 1
                """,
                (raw, streamer_key, raw.lower(), twitch_channel_id),
            ).fetchone()
        return row_to_streamer(row) if row else None

    def list_channel_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT channel_id FROM streamers ORDER BY channel_id"
            ).fetchall()
        return [str(row["channel_id"]) for row in rows]

    def register_streamer(
        self,
        *,
        channel_id: str | None = None,
        channel_login: str | None = None,
        email: str | None,
        display_name: str | None,
        language: str | None,
    ) -> RegistrationResult:
        clean_twitch_channel_id = ""
        if channel_id:
            clean_twitch_channel_id = normalize_channel_id(channel_id)

        clean_channel_login = ""
        if channel_login:
            clean_channel_login = normalize_channel_login(channel_login)

        if not clean_channel_login and not clean_twitch_channel_id:
            raise ValueError("channel_login_required")

        preferred_key = (
            login_streamer_key(clean_channel_login)
            if clean_channel_login
            else clean_twitch_channel_id
        )
        clean_email = normalize_email(email)
        clean_display_name = (display_name or clean_channel_login or "").strip()[:80]
        clean_language = normalize_language(language)
        token = secrets.token_urlsafe(32)
        digest = hash_token(token)
        timestamp = now_ms()

        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT channel_id, created_at
                FROM streamers
                WHERE channel_id = ?
                   OR channel_login = ?
                   OR twitch_channel_id = ?
                   OR channel_id = ?
                LIMIT 1
                """,
                (
                    preferred_key,
                    clean_channel_login,
                    clean_twitch_channel_id,
                    clean_twitch_channel_id,
                ),
            ).fetchone()
            created = existing is None
            streamer_key = preferred_key if created else str(existing["channel_id"])
            created_at = timestamp if created else int(existing["created_at"])
            connection.execute(
                """
                INSERT INTO streamers (
                    channel_id,
                    channel_login,
                    twitch_channel_id,
                    email,
                    display_name,
                    language,
                    token_hash,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_login = excluded.channel_login,
                    twitch_channel_id = excluded.twitch_channel_id,
                    email = excluded.email,
                    display_name = excluded.display_name,
                    language = excluded.language,
                    token_hash = excluded.token_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    streamer_key,
                    clean_channel_login,
                    clean_twitch_channel_id,
                    clean_email,
                    clean_display_name,
                    clean_language,
                    digest,
                    created_at,
                    timestamp,
                ),
            )
            connection.commit()

        streamer = StreamerRecord(
            streamer_key=streamer_key,
            channel_id=clean_twitch_channel_id or streamer_key,
            channel_login=clean_channel_login,
            email=clean_email,
            display_name=clean_display_name,
            language=clean_language,
            created_at=created_at,
            updated_at=timestamp,
        )
        return RegistrationResult(streamer=streamer, token=token, created=created)

    def verify_token(self, channel_id: str, token: str | None) -> bool:
        if not token:
            return False
        raw, streamer_key, twitch_channel_id = self._lookup_values(channel_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT token_hash
                FROM streamers
                WHERE channel_id = ?
                   OR channel_id = ?
                   OR channel_login = ?
                   OR twitch_channel_id = ?
                LIMIT 1
                """,
                (raw, streamer_key, raw.lower(), twitch_channel_id),
            ).fetchone()
        if not row:
            return False
        return hmac.compare_digest(str(row["token_hash"]), hash_token(token.strip()))
