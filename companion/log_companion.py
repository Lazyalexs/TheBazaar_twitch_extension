from __future__ import annotations

import tempfile as _tempfile
from pathlib import Path as _Path
from datetime import datetime as _datetime

_COMPANION_LOG_PATH = _Path(_tempfile.gettempdir()) / "thebazaar_vision_debug.log"

def _companion_log(msg: str) -> None:
    line = f"{_datetime.now().strftime('%H:%M:%S')} [log_comp] {msg}\n"
    try:
        with open(_COMPANION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

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

ITEM_SIZES = {"small", "medium", "large"}
UNKNOWN_ITEM_PREFIX = "unknown:"
DEFAULT_FRAME_WIDTH = 1920
DEFAULT_FRAME_HEIGHT = 1080
PIXEL_BOX_PROFILES: dict[str, dict[str, float]] = {
    "1080p": {
        "frame_width": 1920,
        "frame_height": 1080,
        "board_left": 30,
        "opponent_board_top": 130,
        "board_top": 556.5,
        "socket_step": 157.5,
        "small_width": 132,
        "medium_width": 216,
        "large_width": 324,
        "box_height": 216,
        "pad_x": 9,
        "pad_y": 4.5,
    },
    "720p": {
        "frame_width": 1280,
        "frame_height": 720,
        "board_left": 20,
        "opponent_board_top": 86.5,
        "board_top": 371,
        "socket_step": 105,
        "small_width": 88,
        "medium_width": 144,
        "large_width": 216,
        "box_height": 144,
        "pad_x": 6,
        "pad_y": 3,
    }
}
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
    opponent_board_y: float = 0.13
    board_bottom_y: float | None = None
    socket_step: float = 0.075
    row_break: int | None = None
    small_width: float = 0.07
    medium_width: float = 0.1125
    large_width: float = 0.16875
    box_height: float = 0.2
    pad_x: float = 0.005
    pad_y: float = 0.0037


@dataclass(frozen=True)
class LogDelta:
    text: str
    reset: bool


class BazaarLogState:
    def __init__(
        self,
        templates: dict[str, TemplateInfo],
        calibration: BoxCalibration | None = None,
        visual_resolver: Any | None = None,
    ) -> None:
        self.templates = templates
        self.calibration = calibration or BoxCalibration()
        self.visual_resolver = visual_resolver
        self.instance_to_template: dict[str, str] = {}
        self.instance_to_size: dict[str, str] = {}
        self.board: dict[int, str] = {}
        self.opponent_board: dict[int, str] = {}
        self.stash: dict[int, str] = {}
        self.phase = "unknown"

    def apply_line(self, line: str) -> None:
        self._apply_state(line)
        self._apply_purchase(line)
        self._apply_spawn(line)
        self._apply_move(line)
        self._apply_dispose(line)

    def apply_text(self, text: str) -> None:
        """Apply many newline-separated log lines at once."""
        if not text:
            return
        for line in text.splitlines():
            self.apply_line(line)

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
            self.opponent_board.clear()
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

        entries = [match.groups() for match in SPAWN_RE.finditer(line)]
        player_entries = [entry for entry in entries if entry[1] == "Player"]
        opponent_entries = [entry for entry in entries if entry[1] == "Opponent"]
        hand_entries = [entry for entry in player_entries if entry[2] == "Hand"]
        opponent_hand_entries = [
            entry for entry in opponent_entries if entry[2] == "Hand"
        ]

        if hand_entries:
            self.board.clear()
            for instance_id, _owner, _section, socket, size in hand_entries:
                self._set_board(int(socket), instance_id, size)

        if opponent_hand_entries:
            self.opponent_board.clear()
            for instance_id, _owner, _section, socket, size in opponent_hand_entries:
                self._set_opponent_board(int(socket), instance_id, size)

        for instance_id, _owner, section, socket, size in player_entries:
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
        self.opponent_board = {
            socket: instance_id
            for socket, instance_id in self.opponent_board.items()
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

    def _set_opponent_board(self, socket: int, instance_id: str, size: str | None = None) -> None:
        self._remove_instance(instance_id)
        self.opponent_board[socket] = instance_id
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
        self.opponent_board = {
            socket: current
            for socket, current in self.opponent_board.items()
            if current != instance_id
        }
        self.stash = {
            socket: current
            for socket, current in self.stash.items()
            if current != instance_id
        }

    def payload(self, patch: str) -> dict[str, Any]:
        if self.visual_resolver and hasattr(self.visual_resolver, "begin_frame"):
            self.visual_resolver.begin_frame()
        board_items = self._board_items()
        opponent_items = self._board_items(opponent=True)
        return {
            "patch": patch,
            "hero": None,
            "phase": self.phase,
            "board": [*opponent_items, *board_items],
            "stash": [],
            "skills": [],
        }

    def _board_items(self, opponent: bool = False) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        board = self.opponent_board if opponent else self.board
        for slot, instance_id in sorted(board.items()):
            template_id = self.instance_to_template.get(instance_id)
            if not template_id:
                items.append(self._unknown_board_item(slot, instance_id, opponent))
                continue

            info = self.templates.get(template_id)
            if not info:
                items.append(self._unknown_board_item(slot, instance_id, opponent))
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
                    "bbox": socket_box(slot, size, self.calibration, opponent),
                }
            )
        return items

    def _unknown_board_item(
        self,
        slot: int,
        instance_id: str,
        opponent: bool = False,
    ) -> dict[str, Any]:
        size = self.instance_to_size.get(instance_id, "Small")
        bbox = socket_box(slot, size, self.calibration, opponent)
        match = self._visual_match(slot, instance_id, size, bbox)
        if match is not None:
            return {
                "slot": slot,
                "id": str(match.title),
                "source": "vision",
                "confidence": float(getattr(match, "confidence", 0.99)),
                "tier": getattr(match, "tier", None),
                "enchants": [],
                "cd": getattr(match, "cooldown", None),
                "ammo": None,
                "bbox": bbox,
            }
        return {
            "slot": slot,
            "id": f"{UNKNOWN_ITEM_PREFIX}{instance_id}",
            "source": "game",
            "confidence": 1,
            "tier": None,
            "enchants": [],
            "cd": None,
            "ammo": None,
            "bbox": bbox,
        }

    def _visual_match(
        self,
        slot: int,
        instance_id: str,
        size: str,
        bbox: dict[str, float],
    ) -> Any | None:
        if self.visual_resolver is None:
            return None
        try:
            result = self.visual_resolver.match(slot, instance_id, size, bbox)
            if result is None:
                _companion_log(f"visual_match slot={slot} id={instance_id}: NO MATCH")
            return result
        except Exception as e:
            _companion_log(f"visual_match slot={slot} ERROR: {e}")
            return None


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
    visual_resolver: Any | None = None,
) -> BazaarLogState:
    state = BazaarLogState(templates, calibration, visual_resolver)
    for line in log_text.splitlines():
        state.apply_line(line)
    return state


class LogTailer:
    """Incrementally reads new content appended to log files.

    Tracks byte offset per file. Returns the delta since the previous
    read. Detects truncation (file rotated / new match) and signals a
    reset so callers can rebuild state.
    """

    def __init__(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self._positions: dict[Path, int] = {}
        self._buffer: str = ""
        self._first_read = True

    def reset(self) -> None:
        self._positions.clear()
        self._buffer = ""
        self._first_read = True

    def read_new(self) -> LogDelta:
        """Read all bytes appended to tracked log files since last call.

        Returns LogDelta(text=..., reset=...). `reset=True` when at
        least one file was truncated below its previously seen length
        (i.e. the game started a new match and rotated Player.log) —
        the caller should rebuild any state derived from the log.
        """
        reset = False
        chunks: list[str] = []

        for path in self.paths:
            try:
                stat = path.stat()
            except (FileNotFoundError, OSError):
                # file disappeared since last read; drop any tracked offset
                if path in self._positions:
                    self._positions.pop(path, None)
                    reset = True
                continue

            current_size = stat.st_size
            last_pos = self._positions.get(path, 0)

            if current_size < last_pos:
                # truncated -> new match
                reset = True
                last_pos = 0

            if current_size == last_pos:
                # nothing new
                self._positions[path] = current_size
                continue

            try:
                with path.open("rb") as fh:
                    fh.seek(last_pos)
                    data = fh.read(current_size - last_pos)
            except OSError:
                continue

            self._positions[path] = current_size
            chunks.append(data.decode("utf-8", errors="replace").replace("\r\n", "\n"))

        text = self._buffer + "".join(chunks)
        # keep the incomplete trailing line in the buffer; emit only
        # complete lines so apply_line never sees a half-line.
        if text and not text.endswith("\n"):
            last_nl = text.rfind("\n")
            if last_nl < 0:
                self._buffer = text
                text = ""
            else:
                self._buffer = text[last_nl + 1:]
                text = text[: last_nl + 1]
        else:
            self._buffer = ""

        if reset:
            # we may have to redo state from scratch; tell caller to
            # rebuild but still hand them whatever we have now.
            return LogDelta(text=text, reset=True)
        return LogDelta(text=text, reset=False)


class LogStatsCollector:
    """Mutable accumulator that mirrors summarize_log_text incrementally.

    Use update(text) to feed appended chunks. snapshot() returns a
    frozen LogStats with the running totals.
    """

    def __init__(self) -> None:
        self.purchases = 0
        self.sales = 0
        self.sold_gold = 0
        self.combats = 0
        self.pvp_combats = 0
        self.combat_completions = 0
        self.cards_dealt_events = 0
        self.last_state: str | None = None

    def reset(self) -> None:
        self.__init__()

    def update(self, text: str) -> None:
        if not text:
            return
        from .log_stats import (
            COMBAT_START_RE as _COMBAT,
            SOLD_RE as _SOLD,
            CARDS_DEALT_RE as _DEALT,
        )
        for line in text.splitlines():
            state_match = STATE_RE.search(line)
            if state_match:
                self.last_state = state_match.group(1)
            purchase_match = PURCHASE_RE.search(line)
            if purchase_match and purchase_match.group(3).startswith("Player"):
                self.purchases += 1
            sold_match = _SOLD.search(line)
            if sold_match:
                self.sales += 1
                self.sold_gold += int(sold_match.group(2))
            combat_match = _COMBAT.search(line)
            if combat_match:
                self.combats += 1
                if combat_match.group(1) == "PVPCombatState":
                    self.pvp_combats += 1
            if "Combat simulation completed" in line:
                self.combat_completions += 1
            if _DEALT.search(line):
                self.cards_dealt_events += 1

    def snapshot(self) -> "LogStats":
        from .log_stats import LogStats, phase_from_state
        return LogStats(
            phase=phase_from_state(self.last_state),
            purchases=self.purchases,
            sales=self.sales,
            sold_gold=self.sold_gold,
            combats=self.combats,
            pvp_combats=self.pvp_combats,
            combat_completions=self.combat_completions,
            cards_dealt_events=self.cards_dealt_events,
            last_state=self.last_state,
        )


def normalized_size(size: str | None) -> str:
    clean = str(size or "Small").strip().lower()
    return clean if clean in ITEM_SIZES else "small"


def box_width_for_size(size: str | None, calibration: BoxCalibration) -> float:
    size_key = normalized_size(size)
    if size_key == "large":
        return calibration.large_width
    if size_key == "medium":
        return calibration.medium_width
    return calibration.small_width


def socket_grid_position(
    socket: int,
    calibration: BoxCalibration,
    opponent: bool = False,
) -> tuple[int, float]:
    if opponent:
        return socket, calibration.opponent_board_y
    if (
        calibration.row_break is not None
        and calibration.board_bottom_y is not None
        and socket >= calibration.row_break
    ):
        return socket - calibration.row_break, calibration.board_bottom_y
    return socket, calibration.board_y


def socket_box(
    socket: int,
    size: str,
    calibration: BoxCalibration,
    opponent: bool = False,
) -> dict[str, float]:
    column, row_y = socket_grid_position(socket, calibration, opponent)
    x = calibration.board_x + column * calibration.socket_step - calibration.pad_x
    y = row_y - calibration.pad_y
    width = box_width_for_size(size, calibration) + calibration.pad_x * 2
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


def optional_env_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return int(value)


def optional_env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return float(value)


def first_float(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def parse_resolution(value: str | None) -> tuple[int, int] | None:
    if value is None or value.strip().lower() in {"", "auto", "detect"}:
        return None

    match = re.fullmatch(r"\s*(\d{3,5})\s*[xX]\s*(\d{3,5})\s*", value)
    if not match:
        raise ValueError(f"Invalid resolution: {value!r}. Use 1920x1080 or auto.")

    width, height = (int(match.group(1)), int(match.group(2)))
    if width <= 0 or height <= 0:
        raise ValueError("Resolution values must be positive")
    return width, height


def is_bazaar_game_window_title(title: str) -> bool:
    lower = title.strip().lower()
    return "the bazaar" in lower and "companion" not in lower


def detect_game_window_size() -> tuple[int, int] | None:
    if os.name != "nt":
        return None

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    user32 = ctypes.windll.user32
    candidates: list[tuple[int, int]] = []

    def enum_window(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length <= 0:
            return True

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        if not is_bazaar_game_window_title(title_buffer.value):
            return True

        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width >= 640 and height >= 360:
            candidates.append((width, height))
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(callback(enum_window), 0)
    if not candidates:
        return None

    return max(candidates, key=lambda size: size[0] * size[1])


def resolve_frame_size(args: argparse.Namespace) -> tuple[int, int]:
    if (args.stream_width is None) != (args.stream_height is None):
        raise ValueError("--stream-width and --stream-height must be provided together")
    if args.stream_width is not None and args.stream_height is not None:
        if args.stream_width <= 0 or args.stream_height <= 0:
            raise ValueError("--stream-width and --stream-height must be positive")
        return args.stream_width, args.stream_height

    parsed = parse_resolution(args.stream_resolution)
    if parsed is not None:
        return parsed

    if not args.disable_window_detect:
        detected = detect_game_window_size()
        if detected is not None:
            return detected

    return DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT


def build_calibration(args: argparse.Namespace) -> BoxCalibration:
    profile_name = str(args.box_profile or "").strip().lower()
    if profile_name in {"", "none", "normalized"}:
        profile = None
    else:
        profile = PIXEL_BOX_PROFILES.get(profile_name)
        if profile is None:
            names = ", ".join(sorted(PIXEL_BOX_PROFILES))
            raise ValueError(f"Unknown box profile: {profile_name}. Use normalized or {names}.")

    has_pixel_args = any(
        value is not None
        for value in [
            args.board_left_px,
            args.opponent_board_top_px,
            args.board_top_px,
            args.board_bottom_top_px,
            args.socket_step_px,
            args.socket_9_left_px,
            args.small_width_px,
            args.medium_width_px,
            args.large_width_px,
            args.box_height_px,
            args.pad_x_px,
            args.pad_y_px,
        ]
    ) or profile is not None
    frame_width, frame_height = resolve_frame_size(args)

    if not has_pixel_args:
        return BoxCalibration(
            board_x=args.board_x,
            board_y=args.board_y,
            opponent_board_y=args.opponent_board_y,
            board_bottom_y=args.board_bottom_y,
            socket_step=args.socket_step,
            row_break=args.row_break,
            small_width=args.small_width,
            medium_width=args.medium_width,
            large_width=args.large_width,
            box_height=args.box_height,
            pad_x=args.pad_x,
            pad_y=args.pad_y,
        )

    def profile_px(name: str, axis: str) -> float | None:
        if profile is None:
            return None
        if name not in profile:
            return None
        if axis == "x":
            return profile[name] * frame_width / profile["frame_width"]
        return profile[name] * frame_height / profile["frame_height"]

    board_left_px = first_float(
        args.board_left_px,
        profile_px("board_left", "x"),
        args.board_x * frame_width,
    )
    board_top_px = first_float(
        args.board_top_px,
        profile_px("board_top", "y"),
        args.board_y * frame_height,
    )
    opponent_board_top_px = first_float(
        args.opponent_board_top_px,
        profile_px("opponent_board_top", "y"),
        args.opponent_board_y * frame_height,
    )
    board_bottom_top_px = first_float(
        args.board_bottom_top_px,
        profile_px("board_bottom_top", "y"),
        None if args.board_bottom_y is None else args.board_bottom_y * frame_height,
    )
    if args.socket_9_left_px is not None:
        socket_step_px = (args.socket_9_left_px - board_left_px) / 9
    else:
        socket_step_px = (
            args.socket_step_px
            if args.socket_step_px is not None
            else first_float(
                profile_px("socket_step", "x"),
                args.socket_step * frame_width,
            )
        )

    small_width_px = first_float(
        args.small_width_px,
        profile_px("small_width", "x"),
        args.small_width * frame_width,
    )
    box_height_px = first_float(
        args.box_height_px,
        profile_px("box_height", "y"),
        args.box_height * frame_height,
    )
    medium_width_px = first_float(
        args.medium_width_px,
        profile_px("medium_width", "x"),
        args.medium_width * frame_width,
        box_height_px,
    )
    large_width_px = first_float(
        args.large_width_px,
        profile_px("large_width", "x"),
        args.large_width * frame_width,
        box_height_px * 1.5,
    )
    pad_x_px = first_float(
        args.pad_x_px,
        profile_px("pad_x", "x"),
        args.pad_x * frame_width,
    )
    pad_y_px = first_float(
        args.pad_y_px,
        profile_px("pad_y", "y"),
        args.pad_y * frame_height,
    )

    return BoxCalibration(
        board_x=board_left_px / frame_width,
        board_y=board_top_px / frame_height,
        opponent_board_y=opponent_board_top_px / frame_height,
        board_bottom_y=(
            None if board_bottom_top_px is None else board_bottom_top_px / frame_height
        ),
        socket_step=socket_step_px / frame_width,
        row_break=args.row_break if args.row_break is not None else (
            None if profile is None or "row_break" not in profile else int(profile["row_break"])
        ),
        small_width=small_width_px / frame_width,
        medium_width=medium_width_px / frame_width,
        large_width=large_width_px / frame_width,
        box_height=box_height_px / frame_height,
        pad_x=pad_x_px / frame_width,
        pad_y=pad_y_px / frame_height,
    )


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
    parser.add_argument(
        "--max-send-interval",
        type=float,
        default=env_float("BAZAAR_MAX_SEND_INTERVAL", 15.0),
        help="Republish unchanged state after this many seconds.",
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stream-resolution",
        default=os.environ.get("BAZAAR_STREAM_RESOLUTION", "auto"),
        help="Frame/profile resolution for pixel calibration, for example 1920x1080.",
    )
    parser.add_argument(
        "--box-profile",
        default=os.environ.get("BAZAAR_BOX_PROFILE", "1080p"),
        help="Box geometry profile: 1080p, 720p, or normalized.",
    )
    parser.add_argument(
        "--visual-fallback",
        action="store_true",
        help="Try screenshot/art matching for game-log items without TemplateId.",
    )
    parser.add_argument(
        "--items-data",
        type=Path,
        default=None,
        help="Path to extension/data/items.min.json for visual fallback.",
    )
    parser.add_argument(
        "--visual-threshold",
        type=float,
        default=float(os.environ.get("BAZAAR_VISUAL_THRESHOLD", "0.24")),
    )
    parser.add_argument(
        "--visual-margin",
        type=float,
        default=float(os.environ.get("BAZAAR_VISUAL_MARGIN", "0.035")),
        help="Minimum score gap between the best and second-best visual matches.",
    )
    parser.add_argument(
        "--stream-width",
        type=int,
        default=optional_env_int("BAZAAR_STREAM_WIDTH"),
    )
    parser.add_argument(
        "--stream-height",
        type=int,
        default=optional_env_int("BAZAAR_STREAM_HEIGHT"),
    )
    parser.add_argument("--disable-window-detect", action="store_true")
    parser.add_argument("--board-x", type=float, default=env_float("BAZAAR_BOARD_X", 0.09))
    parser.add_argument("--board-y", type=float, default=env_float("BAZAAR_BOARD_Y", 0.52))
    parser.add_argument(
        "--opponent-board-y",
        type=float,
        default=env_float("BAZAAR_OPPONENT_BOARD_Y", 0.13),
    )
    parser.add_argument(
        "--board-bottom-y",
        type=float,
        default=optional_env_float("BAZAAR_BOARD_BOTTOM_Y"),
    )
    parser.add_argument(
        "--socket-step",
        type=float,
        default=env_float("BAZAAR_SOCKET_STEP", 0.075),
    )
    parser.add_argument(
        "--row-break",
        type=int,
        default=optional_env_int("BAZAAR_ROW_BREAK"),
        help="First socket index on the second board row; unset keeps a single row.",
    )
    parser.add_argument(
        "--small-width",
        type=float,
        default=env_float("BAZAAR_SMALL_WIDTH", 0.07),
    )
    parser.add_argument(
        "--medium-width",
        type=float,
        default=env_float("BAZAAR_MEDIUM_WIDTH", 0.1125),
    )
    parser.add_argument(
        "--large-width",
        type=float,
        default=env_float("BAZAAR_LARGE_WIDTH", 0.16875),
    )
    parser.add_argument(
        "--box-height",
        type=float,
        default=env_float("BAZAAR_BOX_HEIGHT", 0.2),
    )
    parser.add_argument("--pad-x", type=float, default=env_float("BAZAAR_BOX_PAD_X", 0.018))
    parser.add_argument("--pad-y", type=float, default=env_float("BAZAAR_BOX_PAD_Y", 0.005))
    parser.add_argument(
        "--board-left-px",
        "--board-x-px",
        dest="board_left_px",
        type=float,
        default=first_float(
            optional_env_float("BAZAAR_BOARD_LEFT_PX"),
            optional_env_float("BAZAAR_BOARD_X_PX"),
        ),
    )
    parser.add_argument(
        "--board-top-px",
        "--board-y-px",
        dest="board_top_px",
        type=float,
        default=first_float(
            optional_env_float("BAZAAR_BOARD_TOP_PX"),
            optional_env_float("BAZAAR_BOARD_Y_PX"),
        ),
    )
    parser.add_argument(
        "--opponent-board-top-px",
        "--opponent-board-y-px",
        dest="opponent_board_top_px",
        type=float,
        default=first_float(
            optional_env_float("BAZAAR_OPPONENT_BOARD_TOP_PX"),
            optional_env_float("BAZAAR_OPPONENT_BOARD_Y_PX"),
        ),
    )
    parser.add_argument(
        "--board-bottom-top-px",
        "--board-bottom-y-px",
        dest="board_bottom_top_px",
        type=float,
        default=first_float(
            optional_env_float("BAZAAR_BOARD_BOTTOM_TOP_PX"),
            optional_env_float("BAZAAR_BOARD_BOTTOM_Y_PX"),
        ),
    )
    parser.add_argument(
        "--socket-step-px",
        type=float,
        default=optional_env_float("BAZAAR_SOCKET_STEP_PX"),
    )
    parser.add_argument(
        "--socket-9-left-px",
        "--socket-9-x-px",
        dest="socket_9_left_px",
        type=float,
        default=first_float(
            optional_env_float("BAZAAR_SOCKET_9_LEFT_PX"),
            optional_env_float("BAZAAR_SOCKET_9_X_PX"),
        ),
    )
    parser.add_argument(
        "--small-width-px",
        type=float,
        default=optional_env_float("BAZAAR_SMALL_WIDTH_PX"),
    )
    parser.add_argument(
        "--medium-width-px",
        type=float,
        default=optional_env_float("BAZAAR_MEDIUM_WIDTH_PX"),
    )
    parser.add_argument(
        "--large-width-px",
        type=float,
        default=optional_env_float("BAZAAR_LARGE_WIDTH_PX"),
    )
    parser.add_argument(
        "--box-height-px",
        type=float,
        default=optional_env_float("BAZAAR_BOX_HEIGHT_PX"),
    )
    parser.add_argument(
        "--pad-x-px",
        type=float,
        default=optional_env_float("BAZAAR_BOX_PAD_X_PX"),
    )
    parser.add_argument(
        "--pad-y-px",
        type=float,
        default=optional_env_float("BAZAAR_BOX_PAD_Y_PX"),
    )
    args = parser.parse_args()

    cards_cache = args.cards_cache or default_cards_cache(args.game_dir)
    patch, templates = load_templates(cards_cache)
    calibration = build_calibration(args)
    visual_resolver = None
    if args.visual_fallback:
        try:
            from companion.vision_matcher import VisualCardResolver
        except ModuleNotFoundError:
            from vision_matcher import VisualCardResolver

        visual_resolver = VisualCardResolver(
            items_data_path=args.items_data,
            threshold=args.visual_threshold,
            ambiguity_margin=args.visual_margin,
        )
    log_paths = [args.game_dir / "Player-prev.log", args.game_dir / "Player.log"]

    seq = 1
    run_id = f"log-companion-{int(time.time())}"
    last_payload: bytes | None = None
    last_sent_at = 0.0

    while True:
        state = build_state(
            read_log_text(log_paths),
            templates,
            calibration,
            visual_resolver=visual_resolver,
        )
        payload = state.payload(patch)
        payload_key = compact_json(payload)
        now = time.monotonic()

        if (
            args.once
            or payload_key != last_payload
            or now - last_sent_at >= args.max_send_interval
        ):
            snapshot = build_snapshot(seq, run_id, payload)
            if args.dry_run:
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            else:
                print(post_snapshot(args.url, args.channel, args.token, snapshot))
            seq += 1
            last_payload = payload_key
            last_sent_at = now

        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()