from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PURCHASE_RE = re.compile(
    r"Card Purchased: InstanceId: (\S+) - TemplateId([0-9a-f-]{36}) "
    r"- Target:(\S+) - Section(\S+)"
)
SPAWN_RE = re.compile(
    r"\[([^\s\[]+) \[(Player|Opponent)\](?: \[(Hand|Stash)\])? "
    r"\[Socket_(\d+)\] \[(Small|Medium|Large)\]"
)
MOVE_TO_RE = re.compile(
    r"Successfully moved card to: \[([^\s\[]+) \[Player\] "
    r"\[(Hand|Stash)\] \[Socket_(\d+)\] \[(Small|Medium|Large)\]"
)
MOVE_SIMPLE_RE = re.compile(r"Successfully moved card ([^\s]+) to Socket_(\d+)")
DISPOSED_RE = re.compile(r"Cards Disposed: (.*)")
STATE_RE = re.compile(r"State changed from \[[^\]]+\] to \[([^\]]+)\]")

SIZE_SPANS = {"Small": 1, "Medium": 2, "Large": 3}
TIER_MAP = {
    "Bronze": "bronze",
    "Silver": "silver",
    "Gold": "gold",
    "Diamond": "diamond",
}


@dataclass(frozen=True)
class TemplateInfo:
    template_id: str
    title: str
    size: str
    tier: str | None
    cooldown: float | None


@dataclass(frozen=True)
class BoxCalibration:
    board_x: float = 0.09
    board_y: float = 0.52
    socket_step: float = 0.075
    small_width: float = 0.105
    box_height: float = 0.2
    pad_x: float = 0.018
    pad_y: float = 0.005


class BazaarLogState:
    def __init__(
        self,
        templates: dict[str, TemplateInfo],
        calibration: BoxCalibration | None = None,
    ) -> None:
        self.templates = templates
        self.calibration = calibration or BoxCalibration()
        self.instance_to_template: dict[str, str] = {}
        self.instance_to_size: dict[str, str] = {}
        self.board: dict[int, str] = {}
        self.stash: dict[int, str] = {}
        self.phase = "unknown"

    def apply_line(self, line: str) -> None:
        self._apply_state(line)
        self._apply_purchase(line)
        self._apply_spawn(line)
        self._apply_move(line)
        self._apply_dispose(line)

    def _apply_state(self, line: str) -> None:
        match = STATE_RE.search(line)
        if not match:
            return

        state = match.group(1)
        if "CombatState" in state:
            self.phase = "combat"
        elif state in {"ChoiceState", "EncounterState", "ReplayState"}:
            self.phase = "shopping"
        elif state in {"MainMenuState", "HomeState"}:
            self.phase = "menu"
        elif "EndRun" in state:
            self.phase = "game_over"
            self.board.clear()
            self.stash.clear()

    def _apply_purchase(self, line: str) -> None:
        match = PURCHASE_RE.search(line)
        if not match:
            return

        instance_id, template_id, target, section = match.groups()
        self.instance_to_template[instance_id] = template_id.lower()
        info = self.templates.get(template_id.lower())
        if info:
            self.instance_to_size[instance_id] = info.size

        target_match = re.search(r"Player(Storage)?Socket_(\d+)", target)
        if not target_match:
            return

        socket = int(target_match.group(2))
        if section == "Player":
            self._set_board(socket, instance_id, info.size if info else None)
        elif section == "Storage":
            self._set_stash(socket, instance_id, info.size if info else None)

    def _apply_spawn(self, line: str) -> None:
        if "Cards Spawned:" not in line:
            return

        entries = [
            match.groups()
            for match in SPAWN_RE.finditer(line)
            if match.group(2) == "Player"
        ]
        hand_entries = [entry for entry in entries if entry[2] == "Hand"]

        if hand_entries:
            self.board.clear()
            for instance_id, _owner, _section, socket, size in hand_entries:
                self._set_board(int(socket), instance_id, size)

        for instance_id, _owner, section, socket, size in entries:
            if section == "Stash":
                self._set_stash(int(socket), instance_id, size)

    def _apply_move(self, line: str) -> None:
        detailed = MOVE_TO_RE.search(line)
        if detailed:
            instance_id, section, socket, size = detailed.groups()
            if section == "Hand":
                self._set_board(int(socket), instance_id, size)
            else:
                self._set_stash(int(socket), instance_id, size)
            return

        simple = MOVE_SIMPLE_RE.search(line)
        if simple:
            instance_id, socket = simple.groups()
            self._set_board(int(socket), instance_id, self.instance_to_size.get(instance_id))

    def _apply_dispose(self, line: str) -> None:
        match = DISPOSED_RE.search(line)
        if not match:
            return

        disposed = {
            token.strip()
            for token in match.group(1).split("|")
            if token.strip()
        }
        if not disposed:
            return

        self.board = {
            socket: instance_id
            for socket, instance_id in self.board.items()
            if instance_id not in disposed
        }
        self.stash = {
            socket: instance_id
            for socket, instance_id in self.stash.items()
            if instance_id not in disposed
        }

    def _set_board(self, socket: int, instance_id: str, size: str | None = None) -> None:
        self._remove_instance(instance_id)
        self.board[socket] = instance_id
        if size:
            self.instance_to_size[instance_id] = size

    def _set_stash(self, socket: int, instance_id: str, size: str | None = None) -> None:
        self._remove_instance(instance_id)
        self.stash[socket] = instance_id
        if size:
            self.instance_to_size[instance_id] = size

    def _remove_instance(self, instance_id: str) -> None:
        self.board = {
            socket: current
            for socket, current in self.board.items()
            if current != instance_id
        }
        self.stash = {
            socket: current
            for socket, current in self.stash.items()
            if current != instance_id
        }

    def payload(self, patch: str) -> dict[str, Any]:
        return {
            "patch": patch,
            "hero": None,
            "phase": self.phase,
            "board": self._board_items(),
            "stash": [],
            "skills": [],
        }

    def _board_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for slot, instance_id in sorted(self.board.items()):
            template_id = self.instance_to_template.get(instance_id)
            if not template_id:
                continue

            info = self.templates.get(template_id)
            if not info:
                continue

            size = self.instance_to_size.get(instance_id, info.size)
            items.append(
                {
                    "slot": slot,
                    "id": info.title,
                    "source": "game",
                    "confidence": 1,
                    "tier": info.tier,
                    "enchants": [],
                    "cd": info.cooldown,
                    "ammo": None,
                    "bbox": socket_box(slot, size, self.calibration),
                }
            )
        return items


def default_game_dir() -> Path:
    return Path.home() / "AppData" / "LocalLow" / "Tempo Storm" / "The Bazaar"


def default_cards_cache(game_dir: Path) -> Path:
    return game_dir / "prod" / "cache" / "cards.json"


def compact_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def cooldown_seconds(card: dict[str, Any]) -> float | None:
    tiers = card.get("Tiers")
    if not isinstance(tiers, dict):
        return None

    first_tier = next(iter(tiers.values()), {})
    attributes = first_tier.get("Attributes") if isinstance(first_tier, dict) else None
    if not isinstance(attributes, dict):
        return None

    cooldown = attributes.get("CooldownMax")
    if not isinstance(cooldown, (int, float)) or cooldown <= 0:
        return None
    return round(float(cooldown) / 1000, 2)


def load_templates(path: Path) -> tuple[str, dict[str, TemplateInfo]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("cards.json must contain a JSON object keyed by patch version")

    latest_patch = sorted(raw.keys())[-1]
    templates: dict[str, TemplateInfo] = {}
    for card in raw.get(latest_patch, []):
        if not isinstance(card, dict) or card.get("Type") != "Item":
            continue

        template_id = str(card.get("Id", "")).lower()
        title = (
            card.get("Localization", {})
            .get("Title", {})
            .get("Text")
            or card.get("InternalName")
            or template_id
        )
        size = str(card.get("Size") or "Small")
        tier = TIER_MAP.get(str(card.get("StartingTier")), None)
        if template_id and title:
            templates[template_id] = TemplateInfo(
                template_id=template_id,
                title=str(title),
                size=size,
                tier=tier,
                cooldown=cooldown_seconds(card),
            )
    return latest_patch, templates


def read_log_text(paths: list[Path]) -> str:
    parts = []
    for path in paths:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def build_state(
    log_text: str,
    templates: dict[str, TemplateInfo],
    calibration: BoxCalibration | None = None,
) -> BazaarLogState:
    state = BazaarLogState(templates, calibration)
    for line in log_text.splitlines():
        state.apply_line(line)
    return state


def socket_box(socket: int, size: str, calibration: BoxCalibration) -> dict[str, float]:
    span = SIZE_SPANS.get(size, 1)
    x = calibration.board_x + socket * calibration.socket_step - calibration.pad_x
    y = calibration.board_y - calibration.pad_y
    width = (
        calibration.small_width
        + (span - 1) * calibration.socket_step
        + calibration.pad_x * 2
    )
    height = calibration.box_height + calibration.pad_y * 2
    x = max(0, min(0.98, x))
    y = max(0, min(0.98, y))
    return {
        "x": round(x, 4),
        "y": round(y, 4),
        "w": round(max(0.025, min(1 - x, width)), 4),
        "h": round(max(0.025, min(1 - y, height)), 4),
    }


def build_snapshot(seq: int, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "snapshot",
        "seq": seq,
        "sentAt": int(time.time() * 1000),
        "patch": str(payload.pop("patch", "bazaar-log")),
        "runId": run_id,
        "payload": payload,
    }


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return float(value)


def post_snapshot(base_url: str, channel_id: str, token: str, snapshot: dict[str, Any]) -> str:
    url = f"{base_url.rstrip('/')}/v1/companion/{channel_id}/snapshot"
    request = urllib.request.Request(
        url,
        data=compact_json(snapshot),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "TheBazaarLogCompanion/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            return f"{response.status} {body}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return f"{exc.code} {body}"


def main() -> None:
    game_dir = default_game_dir()
    parser = argparse.ArgumentParser(
        description="Publish exact The Bazaar board snapshots from local game logs."
    )
    parser.add_argument("--game-dir", type=Path, default=game_dir)
    parser.add_argument("--cards-cache", type=Path)
    parser.add_argument("--url", default=os.environ.get("EBS_PUBLIC_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--channel", default=os.environ.get("COMPANION_CHANNEL_ID", "dev-channel"))
    parser.add_argument(
        "--token",
        default=os.environ.get("COMPANION_SHARED_TOKEN", "dev-companion-token"),
    )
    parser.add_argument("--interval", type=float, default=1.1)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--board-x", type=float, default=env_float("BAZAAR_BOARD_X", 0.09))
    parser.add_argument("--board-y", type=float, default=env_float("BAZAAR_BOARD_Y", 0.52))
    parser.add_argument(
        "--socket-step",
        type=float,
        default=env_float("BAZAAR_SOCKET_STEP", 0.075),
    )
    parser.add_argument(
        "--small-width",
        type=float,
        default=env_float("BAZAAR_SMALL_WIDTH", 0.105),
    )
    parser.add_argument(
        "--box-height",
        type=float,
        default=env_float("BAZAAR_BOX_HEIGHT", 0.2),
    )
    parser.add_argument("--pad-x", type=float, default=env_float("BAZAAR_BOX_PAD_X", 0.018))
    parser.add_argument("--pad-y", type=float, default=env_float("BAZAAR_BOX_PAD_Y", 0.005))
    args = parser.parse_args()

    cards_cache = args.cards_cache or default_cards_cache(args.game_dir)
    patch, templates = load_templates(cards_cache)
    calibration = BoxCalibration(
        board_x=args.board_x,
        board_y=args.board_y,
        socket_step=args.socket_step,
        small_width=args.small_width,
        box_height=args.box_height,
        pad_x=args.pad_x,
        pad_y=args.pad_y,
    )
    log_paths = [args.game_dir / "Player-prev.log", args.game_dir / "Player.log"]

    seq = 1
    run_id = f"log-companion-{int(time.time())}"
    last_payload: bytes | None = None

    while True:
        state = build_state(read_log_text(log_paths), templates, calibration)
        payload = state.payload(patch)
        payload_key = compact_json(payload)

        if args.once or payload_key != last_payload:
            snapshot = build_snapshot(seq, run_id, payload)
            if args.dry_run:
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            else:
                print(post_snapshot(args.url, args.channel, args.token, snapshot))
            seq += 1
            last_payload = payload_key

        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
