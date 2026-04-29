from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MessageType = Literal["snapshot", "diff", "heartbeat", "reset", "error"]
Phase = Literal["menu", "shopping", "combat", "event", "game_over", "unknown"]


class NormalizedBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class BoardItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: int = Field(ge=0, le=15)
    id: str = Field(min_length=1, max_length=80)
    tier: str | None = Field(default=None, max_length=32)
    enchants: list[str] = Field(default_factory=list, max_length=8)
    cd: float | None = Field(default=None, ge=0)
    ammo: int | None = Field(default=None, ge=0)
    bbox: NormalizedBox | None = None


class StashItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    tier: str | None = Field(default=None, max_length=32)


class SkillItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    tier: str | None = Field(default=None, max_length=32)


class SnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hero: str | None = Field(default=None, max_length=64)
    debugHotspots: bool = False
    day: int | None = Field(default=None, ge=0, le=99)
    gold: int | None = Field(default=None, ge=0, le=999)
    health: int | None = Field(default=None, ge=0, le=999)
    maxHealth: int | None = Field(default=None, ge=0, le=999)
    phase: Phase = "unknown"
    board: list[BoardItem] = Field(default_factory=list, max_length=20)
    stash: list[StashItem] = Field(default_factory=list, max_length=30)
    skills: list[SkillItem] = Field(default_factory=list, max_length=20)


class DiffOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "replace", "remove"]
    path: str = Field(min_length=1, max_length=160)
    value: Any | None = None


class DiffPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[DiffOperation] = Field(default_factory=list, max_length=80)


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=64)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=240)


class PubSubEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[1]
    type: MessageType
    seq: int = Field(ge=0)
    sentAt: int = Field(ge=0)
    patch: str = Field(min_length=1, max_length=32)
    runId: str = Field(min_length=1, max_length=96)
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload_for_type(
        cls,
        payload: dict[str, Any],
        info,
    ) -> dict[str, Any]:
        message_type = info.data.get("type")
        if message_type == "snapshot":
            return SnapshotPayload.model_validate(payload).model_dump(
                exclude_none=True
            )
        if message_type == "diff":
            return DiffPayload.model_validate(payload).model_dump(exclude_none=True)
        if message_type == "heartbeat":
            return HeartbeatPayload.model_validate(payload).model_dump(
                exclude_none=True
            )
        if message_type == "error":
            return ErrorPayload.model_validate(payload).model_dump(exclude_none=True)
        if message_type == "reset":
            return payload
        return payload


def compact_json(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def compact_size_bytes(data: Any) -> int:
    return len(compact_json(data).encode("utf-8"))
