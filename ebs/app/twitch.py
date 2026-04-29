from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .protocol import compact_json
from .security import sign_twitch_ebs_jwt


@dataclass(frozen=True)
class PubSubSendResult:
    status_code: int
    body: str


class TwitchPubSubClient:
    user_agent = "TheBazaarTwitchEBS/0.1"

    def __init__(self, settings: Settings):
        self.settings = settings

    def send_broadcast(
        self,
        *,
        channel_id: str,
        message: dict[str, Any],
        timeout_seconds: int = 10,
    ) -> PubSubSendResult:
        authorization = sign_twitch_ebs_jwt(
            secret_base64=self.settings.twitch_secret_base64,
            owner_id=self.settings.twitch_owner_id,
            channel_id=channel_id,
            ttl_seconds=self.settings.jwt_ttl_seconds,
        )

        payload = {
            "broadcaster_id": channel_id,
            "target": ["broadcast"],
            "message": compact_json(message),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.settings.twitch_pubsub_url,
            data=raw,
            method="POST",
            headers={
                "Authorization": f"Bearer {authorization}",
                "Client-Id": self.settings.twitch_client_id,
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return PubSubSendResult(response.status, body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return PubSubSendResult(exc.code, body)

