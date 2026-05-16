from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .protocol import compact_json
from .security import sign_twitch_ebs_jwt

logger = logging.getLogger("ebs.twitch")


@dataclass(frozen=True)
class PubSubSendResult:
    status_code: int
    body: str


class TwitchPubSubClient:
    user_agent = "TheBazaarTwitchEBS/0.1"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0, read=8.0, write=5.0, pool=5.0
                ),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_broadcast(
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

        client = self._get_client()
        try:
            response = await client.post(
                self.settings.twitch_pubsub_url,
                content=raw,
                headers={
                    "Authorization": f"Bearer {authorization}",
                    "Client-Id": self.settings.twitch_client_id,
                    "Content-Type": "application/json",
                    "User-Agent": self.user_agent,
                },
            )
            return PubSubSendResult(response.status_code, response.text)
        except httpx.RequestError as exc:
            logger.error(
                "twitch_request_error",
                extra={"channel_id": channel_id, "error": str(exc)},
            )
            return PubSubSendResult(status_code=599, body=str(exc))
