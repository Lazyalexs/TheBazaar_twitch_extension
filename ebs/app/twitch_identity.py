from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .database import normalize_channel_login


DEFAULT_TWITCH_GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


@dataclass(frozen=True)
class TwitchIdentity:
    channel_id: str
    login: str
    display_name: str


class TwitchIdentityResolver:
    def __init__(self, client_id: str = DEFAULT_TWITCH_GQL_CLIENT_ID) -> None:
        self.client_id = client_id.strip() or DEFAULT_TWITCH_GQL_CLIENT_ID

    def resolve_login(self, channel_login: str) -> TwitchIdentity:
        login = normalize_channel_login(channel_login)
        body = json.dumps(
            {
                "query": (
                    "query($login:String!){"
                    "user(login:$login){ id login displayName }"
                    "}"
                ),
                "variables": {"login": login},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://gql.twitch.tv/gql",
            data=body,
            method="POST",
            headers={
                "Client-Id": self.client_id,
                "Content-Type": "application/json",
                "User-Agent": "TheBazaarTwitchEBS/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ValueError("twitch_lookup_failed") from exc

        user = _user_from_payload(payload)
        if not user:
            raise ValueError("twitch_login_not_found")

        channel_id = str(user.get("id") or "").strip()
        resolved_login = normalize_channel_login(str(user.get("login") or login))
        display_name = str(user.get("displayName") or resolved_login).strip()
        if not channel_id.isdigit():
            raise ValueError("twitch_lookup_failed")
        return TwitchIdentity(
            channel_id=channel_id,
            login=resolved_login,
            display_name=display_name,
        )


def _user_from_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    user = data.get("user")
    return user if isinstance(user, dict) else None
