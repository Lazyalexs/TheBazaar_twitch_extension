from __future__ import annotations

import argparse
import json
import queue
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace
from typing import Any

import tempfile
from pathlib import Path as _Path

_DIAG_LOG_PATH = _Path(tempfile.gettempdir()) / "thebazaar_vision_debug.log"

def _diag_log(msg: str) -> None:
    from datetime import datetime
    line = f"{datetime.now().strftime('%H:%M:%S')} [companion] {msg}\n"
    try:
        with open(_DIAG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

from companion.log_companion import (
    build_calibration,
    build_snapshot,
    compact_json,
    default_cards_cache,
    default_game_dir,
    load_templates,
    post_snapshot,
    read_log_text,
)
from companion.log_stats import LogStats, summarize_log_text
from companion.secure_store import SecureStoreError, SettingsStore, app_config_dir


DEFAULT_EBS_URL = "https://api.thebazaar-twitch.online"
DEFAULT_CHANNEL_ID = ""
APP_VERSION = "0.8.1-twitch-nick"

TEXT = {
    "ru": {
        "window_title": "The Bazaar Live Board Companion",
        "save": "Сохранить",
        "start": "Старт",
        "stop": "Стоп",
        "test_once": "Тест",
        "connection": "Подключение",
        "ebs_url": "EBS URL",
        "channel_id": "Twitch Nick",
        "companion_token": "Companion Token",
        "paste": "Вставить",
        "show": "Показать",
        "verify": "Проверить",
        "register": "Регистрация",
        "game_folder": "Папка игры",
        "browse": "Обзор",
        "stream": "Стрим",
        "language": "Язык",
        "resolution": "Разрешение",
        "box_profile": "Профиль боксов",
        "visual_fallback": "Визуальное распознавание неизвестных карт",
        "box_calibration": "Калибровка боксов",
        "token_note": "Токен хранится через Windows DPAPI. HTTP разрешен только для localhost.",
        "live_status": "Статус",
        "diagnostics": "Диагностика",
        "server": "Сервер",
        "game": "Игра",
        "phase": "Фаза",
        "board": "Доска",
        "stats": "Статистика",
        "stopped": "Остановлено",
        "running": "Работает",
        "not_connected": "Не подключено",
        "not_checked": "Не проверено",
        "watching_logs": "Читает логи",
        "connecting": "Подключение",
        "already_running": "Уже запущено",
        "publisher_started": "Публикация запущена",
        "publisher_stopped": "Публикация остановлена",
        "settings_loaded": "Настройки загружены",
        "settings_saved": "Настройки сохранены защищенно",
        "secure_storage": "Защищенное хранилище",
        "settings": "Настройки",
        "cannot_start": "Не удалось запустить",
        "test_failed": "Тест не прошел",
        "paste_token": "Вставить токен",
        "clipboard_empty": "Буфер обмена пуст",
        "auth_ok": "Авторизация успешна",
        "auth_failed": "Авторизация не прошла",
        "registration_opened": "Открыта страница регистрации",
        "language_changed": "Язык интерфейса изменен",
        "channel_required": "Twitch Nick обязателен",
        "token_required": "Companion Token обязателен",
        "game_not_found": "Папка игры не найдена",
        "cards_not_found": "cards.json не найден",
        "calibration_hint": "Left/Top двигают боксы игрока. Opp Top двигает боксы соперника. Step меняет расстояние.",
        "clear": "Очистить",
    },
    "en": {
        "window_title": "The Bazaar Live Board Companion",
        "save": "Save",
        "start": "Start",
        "stop": "Stop",
        "test_once": "Test Once",
        "connection": "Connection",
        "ebs_url": "EBS URL",
        "channel_id": "Twitch Nick",
        "companion_token": "Companion Token",
        "paste": "Paste",
        "show": "Show",
        "verify": "Verify",
        "register": "Register",
        "game_folder": "Game Folder",
        "browse": "Browse",
        "stream": "Stream",
        "language": "Language",
        "resolution": "Resolution",
        "box_profile": "Box Profile",
        "visual_fallback": "Visual fallback for unknown cards",
        "box_calibration": "Box Calibration",
        "token_note": "Token is stored with Windows DPAPI. HTTP is allowed only for localhost.",
        "live_status": "Live Status",
        "diagnostics": "Diagnostics",
        "server": "Server",
        "game": "Game",
        "phase": "Phase",
        "board": "Board",
        "stats": "Stats",
        "stopped": "Stopped",
        "running": "Running",
        "not_connected": "Not connected",
        "not_checked": "Not checked",
        "watching_logs": "Watching logs",
        "connecting": "Connecting",
        "already_running": "Already running",
        "publisher_started": "Publisher started",
        "publisher_stopped": "Publisher stopped",
        "settings_loaded": "Settings loaded",
        "settings_saved": "Settings saved securely",
        "secure_storage": "Secure storage",
        "settings": "Settings",
        "cannot_start": "Cannot start",
        "test_failed": "Test failed",
        "paste_token": "Paste token",
        "clipboard_empty": "Clipboard is empty",
        "auth_ok": "Authorization OK",
        "auth_failed": "Authorization failed",
        "registration_opened": "Registration page opened",
        "language_changed": "Interface language changed",
        "channel_required": "Twitch Nick is required",
        "token_required": "Companion Token is required",
        "game_not_found": "Game folder not found",
        "cards_not_found": "cards.json not found",
        "calibration_hint": "Left/Top move player boxes. Opp Top moves opponent boxes. Step changes spacing.",
        "clear": "Clear",
    },
}


@dataclass(frozen=True)
class AppConfig:
    ebs_url: str
    channel_id: str
    token: str
    language: str
    game_dir: Path
    stream_resolution: str
    box_profile: str
    board_left_px: float | None
    board_top_px: float | None
    opponent_board_top_px: float | None
    socket_step_px: float | None
    small_width_px: float | None
    medium_width_px: float | None
    large_width_px: float | None
    box_height_px: float | None
    pad_x_px: float | None
    pad_y_px: float | None
    visual_fallback: bool
    interval: float
    max_send_interval: float


@dataclass(frozen=True)
class PublishStatus:
    ok: bool
    message: str
    seq: int
    phase: str
    board_count: int
    board_names: list[str]
    stats: LogStats | None


def validate_server_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme == "https" and parsed.netloc:
        return cleaned
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
        return cleaned
    raise ValueError("EBS URL должен быть HTTPS. HTTP разрешен только для localhost.")


def optional_float(value: str, field_name: str) -> float | None:
    clean = value.strip().replace(",", ".")
    if not clean:
        return None
    try:
        return float(clean)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def calibration_args(config: AppConfig) -> SimpleNamespace:
    return SimpleNamespace(
        stream_resolution=config.stream_resolution,
        stream_width=None,
        stream_height=None,
        disable_window_detect=False,
        box_profile=config.box_profile,
        board_x=0.09,
        board_y=0.52,
        opponent_board_y=0.13,
        board_bottom_y=None,
        socket_step=0.075,
        row_break=None,
        small_width=0.07,
        medium_width=0.1125,
        large_width=0.16875,
        box_height=0.2,
        pad_x=0.005,
        pad_y=0.0037,
        board_left_px=config.board_left_px,
        board_top_px=config.board_top_px,
        opponent_board_top_px=config.opponent_board_top_px,
        board_bottom_top_px=None,
        socket_step_px=config.socket_step_px,
        socket_9_left_px=None,
        small_width_px=config.small_width_px,
        medium_width_px=config.medium_width_px,
        large_width_px=config.large_width_px,
        box_height_px=config.box_height_px,
        pad_x_px=config.pad_x_px,
        pad_y_px=config.pad_y_px,
    )


def calibration_summary(calibration: Any) -> str:
    bottom_y = (
        "none"
        if calibration.board_bottom_y is None
        else f"{calibration.board_bottom_y:.4f}"
    )
    return (
        "geometry "
        f"x={calibration.board_x:.4f}, y={calibration.board_y:.4f}, "
        f"bottom_y={bottom_y}, row_break={calibration.row_break}, "
        f"step={calibration.socket_step:.4f}, "
        f"small={calibration.small_width + calibration.pad_x * 2:.4f}, "
        f"medium={calibration.medium_width + calibration.pad_x * 2:.4f}, "
        f"large={calibration.large_width + calibration.pad_x * 2:.4f}, "
        f"h={calibration.box_height + calibration.pad_y * 2:.4f}"
    )


def create_visual_resolver(enabled: bool) -> Any | None:
    if not enabled:
        _diag_log("visual resolver DISABLED")
        return None
    try:
        from companion.vision_matcher import VisualCardResolver
        _diag_log("visual resolver CREATED")
        return VisualCardResolver()
    except ImportError as e:
        _diag_log(f"visual resolver IMPORT FAILED: {e}")
        return None


class PublisherThread(threading.Thread):
    def __init__(
        self,
        config: AppConfig,
        output: queue.Queue[PublishStatus],
        stop_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.config = config
        self.output = output
        self.stop_event = stop_event

    def run(self) -> None:
        try:
            cards_cache = default_cards_cache(self.config.game_dir)
            patch, templates = load_templates(cards_cache)
            calibration = build_calibration(calibration_args(self.config))
            visual_resolver = create_visual_resolver(self.config.visual_fallback)
            log_paths = [
                self.config.game_dir / "Player-prev.log",
                self.config.game_dir / "Player.log",
            ]
            from companion.log_companion import BazaarLogState, LogTailer, LogStatsCollector
            seq = 1
            run_id = f"desktop-companion-{int(time.time())}"
            last_payload: bytes | None = None
            last_sent_at = 0.0
            self.output.put(
                PublishStatus(
                    ok=True,
                    message=(
                        f"{APP_VERSION}; Loaded patch {patch}, "
                        f"{len(templates)} item templates; "
                        f"{calibration_summary(calibration)}; "
                        f"vision={'on' if visual_resolver else 'off'}"
                    ),
                    seq=0,
                    phase="starting",
                    board_count=0,
                    board_names=[],
                    stats=None,
                )
            )

            tailer = LogTailer(log_paths)
            state = BazaarLogState(templates, calibration, visual_resolver=visual_resolver)
            stats_collector = LogStatsCollector()

            while not self.stop_event.is_set():
                delta = tailer.read_new()
                if delta.reset:
                    state = BazaarLogState(templates, calibration, visual_resolver=visual_resolver)
                    stats_collector.reset()
                state.apply_text(delta.text)
                stats_collector.update(delta.text)
                stats = stats_collector.snapshot()
                payload = state.payload(patch)
                payload_key = compact_json(payload)
                now = time.monotonic()
                should_send = (
                    payload_key != last_payload
                    or now - last_sent_at >= self.config.max_send_interval
                )

                if should_send:
                    board_names = [
                        str(item["id"])
                        for item in [
                            *payload.get("board", []),
                            *payload.get("opponentBoard", []),
                        ]
                    ]
                    snapshot = build_snapshot(seq, run_id, payload)
                    response = post_snapshot(
                        self.config.ebs_url,
                        self.config.channel_id,
                        self.config.token,
                        snapshot,
                    )
                    self.output.put(
                        PublishStatus(
                            ok=response.startswith("200 "),
                            message=response,
                            seq=seq,
                            phase=str(snapshot["payload"].get("phase", "unknown")),
                            board_count=len(board_names),
                            board_names=board_names,
                            stats=stats,
                        )
                    )
                    seq += 1
                    last_payload = payload_key
                    last_sent_at = now

                self.stop_event.wait(self.config.interval)
        except Exception as exc:
            self.output.put(
                PublishStatus(
                    ok=False,
                    message=f"{type(exc).__name__}: {exc}",
                    seq=0,
                    phase="error",
                    board_count=0,
                    board_names=[],
                    stats=None,
                )
            )


class CompanionApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.store = SettingsStore()
        saved_settings = self.store.load()

        self.language = tk.StringVar(value=str(saved_settings.get("language") or "ru"))
        # (key, widget, attribute) — updated on language change
        self._translated: list[tuple[str, tk.Widget, str]] = []

        self.title(f"{self.t('window_title')} {APP_VERSION}")
        self.geometry("980x720")
        self.minsize(900, 640)

        self.status_queue: queue.Queue[PublishStatus] = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.worker: PublisherThread | None = None

        self.ebs_url = tk.StringVar(value=DEFAULT_EBS_URL)
        self.channel_id = tk.StringVar(value=DEFAULT_CHANNEL_ID)
        self.token = tk.StringVar(value="")
        self.game_dir = tk.StringVar(value=str(default_game_dir()))
        self.stream_resolution = tk.StringVar(value="auto")
        self.box_profile = tk.StringVar(value="1080p")
        self.board_left_px = tk.StringVar(value="")
        self.board_top_px = tk.StringVar(value="")
        self.opponent_board_top_px = tk.StringVar(value="")
        self.socket_step_px = tk.StringVar(value="")
        self.small_width_px = tk.StringVar(value="")
        self.medium_width_px = tk.StringVar(value="")
        self.large_width_px = tk.StringVar(value="")
        self.box_height_px = tk.StringVar(value="")
        self.pad_x_px = tk.StringVar(value="")
        self.pad_y_px = tk.StringVar(value="")
        self.visual_fallback = tk.BooleanVar(value=True)
        self.show_token = tk.BooleanVar(value=False)
        self.state_text = tk.StringVar(value=self.t("stopped"))
        self.server_text = tk.StringVar(value=self.t("not_connected"))
        self.game_text = tk.StringVar(value=self.t("not_checked"))
        self.phase_text = tk.StringVar(value="-")
        self.board_text = tk.StringVar(value="-")
        self.stats_text = tk.StringVar(value="-")

        self._configure_style()
        self._build_ui()
        self._load_settings(saved_settings)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._drain_status_queue)

    def t(self, key: str) -> str:
        language = self.language.get() if hasattr(self, "language") else "ru"
        return TEXT.get(language, TEXT["ru"]).get(key, TEXT["en"].get(key, key))

    def _register_translation(self, widget: tk.Widget, key: str, attribute: str = "text") -> tk.Widget:
        """Track widget so its text can be refreshed when language changes."""
        self._translated.append((key, widget, attribute))
        return widget

    def _configure_style(self) -> None:
        self.configure(bg="#071014")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#071014", foreground="#f6f1e8", fieldbackground="#0c171d")
        style.configure("TLabel", background="#071014", foreground="#f6f1e8")
        style.configure("Muted.TLabel", foreground="#b9afa0")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Card.TFrame", background="#0d171d", relief="solid", borderwidth=1)
        style.configure("TButton", padding=(12, 8))
        style.configure("Danger.TButton", foreground="#fff4ed")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=f"The Bazaar Live Board {APP_VERSION}", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        actions = ttk.Frame(header)
        actions.grid(row=0, column=1, sticky="e", padx=(12, 18))
        self._register_translation(
            ttk.Label(actions, text=self.t("language")), "language"
        ).pack(side="left", padx=(0, 6))

        language_combo: ttk.Combobox = ttk.Combobox(
            actions,
            textvariable=self.language,
            values=["ru", "en"],
            state="readonly",
            width=5,
        )
        language_combo.pack(side="left", padx=(0, 12))
        language_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        self._register_translation(ttk.Button(actions, text=self.t("save"), command=self._save_settings), "save").pack(side="left")
        self._register_translation(ttk.Button(actions, text=self.t("start"), command=self._start), "start").pack(side="left", padx=(8, 0))
        self._register_translation(ttk.Button(actions, text=self.t("stop"), command=self._stop), "stop").pack(side="left", padx=(8, 0))
        self._register_translation(ttk.Button(actions, text=self.t("test_once"), command=self._test_once), "test_once").pack(side="left", padx=(8, 0))
        ttk.Label(
            header,
            textvariable=self.state_text,
            style="Muted.TLabel",
        ).grid(row=0, column=2, sticky="e")

        settings = self._register_translation(ttk.LabelFrame(root, text=self.t("connection")), "connection")
        settings.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        settings.columnconfigure(1, weight=1)
        self._field(settings, 0, "ebs_url", self.ebs_url)
        self._field(settings, 1, "channel_id", self.channel_id)
        self._token_field(settings, 2)

        self._register_translation(ttk.Label(settings, text=self.t("game_folder")), "game_folder").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        game_row = ttk.Frame(settings)
        game_row.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
        game_row.columnconfigure(0, weight=1)
        ttk.Entry(game_row, textvariable=self.game_dir).grid(row=0, column=0, sticky="ew")
        self._register_translation(ttk.Button(game_row, text=self.t("browse"), command=self._browse_game_dir), "browse").grid(row=0, column=1, padx=(8, 0))

        options = self._register_translation(ttk.LabelFrame(root, text=self.t("stream")), "stream")
        options.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        options.columnconfigure(1, weight=1)
        self._combo(options, 0, "resolution", self.stream_resolution, ["auto", "1920x1080", "1280x720"])
        self._combo(options, 1, "box_profile", self.box_profile, ["1080p", "720p", "normalized"])
        self._register_translation(ttk.Checkbutton(
            options,
            text=self.t("visual_fallback"),
            variable=self.visual_fallback,
        ), "visual_fallback").grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(4, 0))
        self._calibration_panel(options, 3)

        self._register_translation(ttk.Label(
            options,
            text=self.t("token_note"),
            wraplength=360,
            style="Muted.TLabel",
        ), "token_note").grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 4))

        live = self._register_translation(ttk.LabelFrame(root, text=self.t("live_status")), "live_status")
        live.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        live.columnconfigure(1, weight=1)
        self._status_row(live, 0, "server", self.server_text)
        self._status_row(live, 1, "game", self.game_text)
        self._status_row(live, 2, "phase", self.phase_text)
        self._status_row(live, 3, "board", self.board_text)
        self._status_row(live, 4, "stats", self.stats_text)

        diagnostics = ttk.LabelFrame(root, text=self.t("diagnostics"))
        diagnostics.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        diagnostics.rowconfigure(0, weight=1)
        diagnostics.columnconfigure(0, weight=1)
        self.log_box = tk.Text(
            diagnostics,
            height=16,
            bg="#0b151a",
            fg="#f6f1e8",
            insertbackground="#f6f1e8",
            relief="flat",
            wrap="word",
        )
        self.log_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._append_log(f"Build: {APP_VERSION}")
        self._append_log(f"Config: {self.store.path}")

    def _field(
        self,
        parent: ttk.Widget,
        row: int,
        key: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> ttk.Entry:
        self._register_translation(ttk.Label(parent, text=self.t(key)), key).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        self._attach_entry_helpers(entry)
        return entry

    def _token_field(self, parent: ttk.Widget, row: int) -> None:
        self._register_translation(ttk.Label(parent, text=self.t("companion_token")), "companion_token").grid(row=row, column=0, sticky="w", padx=10, pady=6)
        token_row = ttk.Frame(parent)
        token_row.grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        token_row.columnconfigure(0, weight=1)

        self.token_entry = ttk.Entry(token_row, textvariable=self.token, show="*")
        self.token_entry.grid(row=0, column=0, sticky="ew")
        self._attach_entry_helpers(self.token_entry)
        self._register_translation(ttk.Button(token_row, text=self.t("paste"), command=self._paste_token), "paste").grid(row=0, column=1, padx=(8, 0))
        self._register_translation(ttk.Checkbutton(
            token_row,
            text=self.t("show"),
            variable=self.show_token,
            command=self._toggle_token_visibility,
        ), "show").grid(row=0, column=2, padx=(8, 0))
        self._register_translation(ttk.Button(token_row, text=self.t("verify"), command=self._verify_auth), "verify").grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._register_translation(ttk.Button(token_row, text=self.t("register"), command=self._open_registration), "register").grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0))

    def _attach_entry_helpers(self, entry: ttk.Entry) -> None:
        def edit(action: str) -> str:
            entry.event_generate(action)
            return "break"

        def select_all() -> str:
            entry.selection_range(0, "end")
            entry.icursor("end")
            return "break"

        entry.bind("<Control-a>", lambda _event: select_all())
        entry.bind("<Control-A>", lambda _event: select_all())
        entry.bind("<Control-v>", lambda _event: edit("<<Paste>>"))
        entry.bind("<Control-V>", lambda _event: edit("<<Paste>>"))
        entry.bind("<Shift-Insert>", lambda _event: edit("<<Paste>>"))
        entry.bind("<Control-c>", lambda _event: edit("<<Copy>>"))
        entry.bind("<Control-C>", lambda _event: edit("<<Copy>>"))
        entry.bind("<Control-x>", lambda _event: edit("<<Cut>>"))
        entry.bind("<Control-X>", lambda _event: edit("<<Cut>>"))

        menu = tk.Menu(entry, tearoff=False)
        menu.add_command(label="Cut", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: entry.event_generate("<<Copy>>"))
        # Known limitation: context-menu stays in original language until app restart
        menu.add_command(label=self.t("paste"), command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select all", command=select_all)

        def show_menu(event: tk.Event) -> str:
            menu.tk_popup(event.x_root, event.y_root)
            return "break"

        entry.bind("<Button-3>", show_menu)

    def _paste_token(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(self.t("paste_token"), self.t("clipboard_empty"))
            return
        if self.token_entry.selection_present():
            self.token_entry.delete("sel.first", "sel.last")
        self.token_entry.insert("insert", text.strip())
        self.token_entry.focus_set()

    def _toggle_token_visibility(self) -> None:
        self.token_entry.configure(show="" if self.show_token.get() else "*")

    def _open_registration(self) -> None:
        try:
            ebs_url = validate_server_url(self.ebs_url.get())
        except Exception as exc:
            messagebox.showerror(self.t("settings"), str(exc))
            return
        lang = urllib.parse.quote(self.language.get() if self.language.get() in TEXT else "ru")
        webbrowser.open(f"{ebs_url}/register?lang={lang}")
        self._append_log(self.t("registration_opened"))

    def _verify_auth(self) -> None:
        try:
            ebs_url = validate_server_url(self.ebs_url.get())
            channel_id = self.channel_id.get().strip()
            token = self.token.get().strip()
            if not channel_id:
                raise ValueError(self.t("channel_required"))
            if not token:
                raise ValueError(self.t("token_required"))

            body = json.dumps(
                {"channelLogin": channel_id, "token": token},
                ensure_ascii=False,
            ).encode("utf-8")
            request = urllib.request.Request(
                f"{ebs_url}/api/companion/verify",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
            self.server_text.set("OK")
            self._append_log(
                f"{self.t('auth_ok')}: "
                f"{result.get('channelLogin') or result.get('channelId', channel_id)}"
            )
            messagebox.showinfo(self.t("verify"), self.t("auth_ok"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            self.server_text.set(self.t("auth_failed"))
            self._append_log(f"{self.t('auth_failed')}: HTTP {exc.code} {details}")
            messagebox.showerror(self.t("verify"), f"HTTP {exc.code}: {details}")
        except Exception as exc:
            self.server_text.set(self.t("auth_failed"))
            self._append_log(f"{self.t('auth_failed')}: {exc}")
            messagebox.showerror(self.t("verify"), str(exc))

    def _combo(
        self,
        parent: ttk.Widget,
        row: int,
        key: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> None:
        self._register_translation(ttk.Label(parent, text=self.t(key)), key).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row,
            column=1,
            sticky="ew",
            padx=10,
            pady=6,
        )

    def _calibration_panel(self, parent: ttk.Widget, row: int) -> None:
        panel = self._register_translation(ttk.LabelFrame(parent, text=self.t("box_calibration")), "box_calibration")
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))
        for column in range(3):
            panel.columnconfigure(column, weight=1)

        fields = [
            ("Left px", self.board_left_px),
            ("Top px", self.board_top_px),
            ("Step px", self.socket_step_px),
            ("Opp Top", self.opponent_board_top_px),
            ("Small W", self.small_width_px),
            ("Medium W", self.medium_width_px),
            ("Large W", self.large_width_px),
            ("Height", self.box_height_px),
            ("Pad X", self.pad_x_px),
            ("Pad Y", self.pad_y_px),
        ]
        for index, (label, variable) in enumerate(fields):
            self._calibration_field(
                panel,
                row=index // 3,
                column=index % 3,
                label=label,
                variable=variable,
            )

        actions = ttk.Frame(panel)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 4))
        ttk.Button(actions, text="720p", command=self._set_720p_calibration).pack(side="left")
        ttk.Button(actions, text="1080p", command=self._set_1080p_calibration).pack(side="left", padx=6)
        self._register_translation(ttk.Button(actions, text=self.t("clear"), command=self._clear_calibration), "clear").pack(side="left")

        self._register_translation(ttk.Label(
            panel,
            text=self.t("calibration_hint"),
            wraplength=420,
            style="Muted.TLabel",
        ), "calibration_hint").grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))

    def _calibration_field(
        self,
        parent: ttk.Widget,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=column, sticky="ew", padx=6, pady=4)
        cell.columnconfigure(0, weight=1)
        ttk.Label(cell, text=label, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(cell, textvariable=variable, width=9)
        entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self._attach_entry_helpers(entry)

    def _open_calibration(self) -> None:
        window = tk.Toplevel(self)
        window.title("Box Calibration")
        window.configure(bg="#071014")
        window.transient(self)
        window.resizable(False, False)

        frame = ttk.Frame(window, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        fields = [
            ("Left px", self.board_left_px, "1080p default 30; move all boxes right/left"),
            ("Top px", self.board_top_px, "1080p default 556.5; move all boxes up/down"),
            ("Opponent Top px", self.opponent_board_top_px, "1080p default 130; move opponent boxes up/down"),
            ("Step px", self.socket_step_px, "1080p default 157.5; distance between sockets"),
            ("Small W px", self.small_width_px, "1080p default 132"),
            ("Medium W px", self.medium_width_px, "1080p default 216"),
            ("Large W px", self.large_width_px, "1080p default 324"),
            ("Height px", self.box_height_px, "1080p default 216"),
            ("Pad X px", self.pad_x_px, "1080p default 9"),
            ("Pad Y px", self.pad_y_px, "1080p default 4.5"),
        ]
        for row, (label, variable, hint) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            entry = ttk.Entry(frame, textvariable=variable, width=14)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            self._attach_entry_helpers(entry)
            ttk.Label(frame, text=hint, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=(10, 0), pady=4)

        actions = ttk.Frame(frame)
        actions.grid(row=len(fields), column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Button(actions, text="Use 1080p defaults", command=self._set_1080p_calibration).pack(side="left")
        ttk.Button(actions, text="Use 720p defaults", command=self._set_720p_calibration).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Clear", command=self._clear_calibration).pack(side="left", padx=8)
        ttk.Button(actions, text="Save", command=lambda: [self._save_settings(), window.destroy()]).pack(side="right")

    def _set_1080p_calibration(self) -> None:
        self.stream_resolution.set("1920x1080")
        self.box_profile.set("1080p")
        self.board_left_px.set("30")
        self.board_top_px.set("556.5")
        self.opponent_board_top_px.set("130")
        self.socket_step_px.set("157.5")
        self.small_width_px.set("132")
        self.medium_width_px.set("216")
        self.large_width_px.set("324")
        self.box_height_px.set("216")
        self.pad_x_px.set("9")
        self.pad_y_px.set("4.5")

    def _set_720p_calibration(self) -> None:
        self.stream_resolution.set("1280x720")
        self.box_profile.set("720p")
        self.board_left_px.set("20")
        self.board_top_px.set("371")
        self.opponent_board_top_px.set("86.5")
        self.socket_step_px.set("105")
        self.small_width_px.set("88")
        self.medium_width_px.set("144")
        self.large_width_px.set("216")
        self.box_height_px.set("144")
        self.pad_x_px.set("6")
        self.pad_y_px.set("3")

    def _clear_calibration(self) -> None:
        for variable in [
            self.board_left_px,
            self.board_top_px,
            self.opponent_board_top_px,
            self.socket_step_px,
            self.small_width_px,
            self.medium_width_px,
            self.large_width_px,
            self.box_height_px,
            self.pad_x_px,
            self.pad_y_px,
        ]:
            variable.set("")

    def _status_row(self, parent: ttk.Widget, row: int, key: str, variable: tk.StringVar) -> None:
        self._register_translation(ttk.Label(parent, text=self.t(key), style="Muted.TLabel"), key).grid(row=row, column=0, sticky="nw", padx=10, pady=7)
        ttk.Label(parent, textvariable=variable, wraplength=370).grid(row=row, column=1, sticky="ew", padx=10, pady=7)

    def _load_settings(self, data: dict[str, Any] | None = None) -> None:
        data = data if data is not None else self.store.load()
        def saved_text(key: str) -> str:
            value = data.get(key)
            return "" if value is None else str(value)

        self.language.set(str(data.get("language") or self.language.get() or "ru"))
        self.ebs_url.set(str(data.get("ebsUrl") or DEFAULT_EBS_URL))
        self.channel_id.set(
            str(data.get("channelLogin") or data.get("channelId") or DEFAULT_CHANNEL_ID)
        )
        self.token.set(str(data.get("token") or ""))
        self.game_dir.set(str(data.get("gameDir") or default_game_dir()))
        self.stream_resolution.set(str(data.get("streamResolution") or "auto"))
        self.box_profile.set(str(data.get("boxProfile") or "1080p"))
        self.board_left_px.set(saved_text("boardLeftPx"))
        self.board_top_px.set(saved_text("boardTopPx"))
        self.opponent_board_top_px.set(saved_text("opponentBoardTopPx"))
        self.socket_step_px.set(saved_text("socketStepPx"))
        self.small_width_px.set(saved_text("smallWidthPx"))
        self.medium_width_px.set(saved_text("mediumWidthPx"))
        self.large_width_px.set(saved_text("largeWidthPx"))
        self.box_height_px.set(saved_text("boxHeightPx"))
        self.pad_x_px.set(saved_text("padXPx"))
        self.pad_y_px.set(saved_text("padYPx"))
        self.visual_fallback.set(bool(data.get("visualFallback", True)))
        self._append_log(self.t("settings_loaded"))

    def _current_settings_payload(self) -> dict[str, Any]:
        return {
            "ebsUrl": self.ebs_url.get().strip() or DEFAULT_EBS_URL,
            "channelLogin": self.channel_id.get().strip() or DEFAULT_CHANNEL_ID,
            "channelId": self.channel_id.get().strip() or DEFAULT_CHANNEL_ID,
            "token": self.token.get().strip(),
            "language": self.language.get().strip() if self.language.get() in TEXT else "ru",
            "gameDir": self.game_dir.get().strip() or str(default_game_dir()),
            "streamResolution": self.stream_resolution.get().strip() or "auto",
            "boxProfile": self.box_profile.get().strip() or "1080p",
            "boardLeftPx": self.board_left_px.get().strip(),
            "boardTopPx": self.board_top_px.get().strip(),
            "opponentBoardTopPx": self.opponent_board_top_px.get().strip(),
            "socketStepPx": self.socket_step_px.get().strip(),
            "smallWidthPx": self.small_width_px.get().strip(),
            "mediumWidthPx": self.medium_width_px.get().strip(),
            "largeWidthPx": self.large_width_px.get().strip(),
            "boxHeightPx": self.box_height_px.get().strip(),
            "padXPx": self.pad_x_px.get().strip(),
            "padYPx": self.pad_y_px.get().strip(),
            "visualFallback": self.visual_fallback.get(),
        }

    def _on_language_change(self, _event: tk.Event | None = None) -> None:
        if self.language.get() not in TEXT:
            self.language.set("ru")
        self.title(f"{self.t('window_title')} {APP_VERSION}")
        self._refresh_translations()
        self._append_log(self.t("language_changed"))

    def _refresh_translations(self) -> None:
        """Update text on all registered translatable widgets to the current language."""
        for key, widget, attribute in self._translated:
            try:
                widget.configure(**{attribute: self.t(key)})
            except tk.TclError:
                pass  # widget destroyed
        # also refresh static labels via state-vars where applicable
        if self.state_text.get() in (
            TEXT["ru"]["stopped"], TEXT["en"]["stopped"],
            TEXT["ru"]["running"], TEXT["en"]["running"],
        ):
            self.state_text.set(
                self.t("running") if (self.worker and self.worker.is_alive())
                else self.t("stopped")
            )
        if self.server_text.get() in (TEXT["ru"]["not_connected"], TEXT["en"]["not_connected"]):
            self.server_text.set(self.t("not_connected"))
        if self.game_text.get() in (TEXT["ru"]["not_checked"], TEXT["en"]["not_checked"]):
            self.game_text.set(self.t("not_checked"))

    def _save_settings(self) -> None:
        try:
            config = self._read_config()
            self.store.save(
                {
                    "ebsUrl": config.ebs_url,
                    "channelLogin": config.channel_id,
                    "channelId": config.channel_id,
                    "token": config.token,
                    "language": config.language,
                    "gameDir": str(config.game_dir),
                    "streamResolution": config.stream_resolution,
                    "boxProfile": config.box_profile,
                    "boardLeftPx": config.board_left_px,
                    "boardTopPx": config.board_top_px,
                    "opponentBoardTopPx": config.opponent_board_top_px,
                    "socketStepPx": config.socket_step_px,
                    "smallWidthPx": config.small_width_px,
                    "mediumWidthPx": config.medium_width_px,
                    "largeWidthPx": config.large_width_px,
                    "boxHeightPx": config.box_height_px,
                    "padXPx": config.pad_x_px,
                    "padYPx": config.pad_y_px,
                    "visualFallback": config.visual_fallback,
                }
            )
            self._append_log(self.t("settings_saved"))
        except SecureStoreError as exc:
            messagebox.showerror(self.t("secure_storage"), str(exc))
        except Exception as exc:
            messagebox.showerror(self.t("settings"), str(exc))

    def _read_config(self) -> AppConfig:
        ebs_url = validate_server_url(self.ebs_url.get())
        channel_id = self.channel_id.get().strip()
        token = self.token.get().strip()
        language = self.language.get().strip() or "ru"
        game_dir = Path(self.game_dir.get()).expanduser()
        if not channel_id:
            raise ValueError(self.t("channel_required"))
        if not token:
            raise ValueError(self.t("token_required"))
        if not game_dir.exists():
            raise ValueError(f"{self.t('game_not_found')}: {game_dir}")
        if not default_cards_cache(game_dir).exists():
            raise ValueError(f"{self.t('cards_not_found')}: {default_cards_cache(game_dir)}")
        return AppConfig(
            ebs_url=ebs_url,
            channel_id=channel_id,
            token=token,
            language=language if language in TEXT else "ru",
            game_dir=game_dir,
            stream_resolution=self.stream_resolution.get().strip() or "auto",
            box_profile=self.box_profile.get().strip() or "1080p",
            board_left_px=optional_float(self.board_left_px.get(), "Left px"),
            board_top_px=optional_float(self.board_top_px.get(), "Top px"),
            opponent_board_top_px=optional_float(
                self.opponent_board_top_px.get(),
                "Opponent Top px",
            ),
            socket_step_px=optional_float(self.socket_step_px.get(), "Step px"),
            small_width_px=optional_float(self.small_width_px.get(), "Small W px"),
            medium_width_px=optional_float(self.medium_width_px.get(), "Medium W px"),
            large_width_px=optional_float(self.large_width_px.get(), "Large W px"),
            box_height_px=optional_float(self.box_height_px.get(), "Height px"),
            pad_x_px=optional_float(self.pad_x_px.get(), "Pad X px"),
            pad_y_px=optional_float(self.pad_y_px.get(), "Pad Y px"),
            visual_fallback=self.visual_fallback.get(),
            interval=1.1,
            max_send_interval=15.0,
        )

    def _browse_game_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.game_dir.get())
        if selected:
            self.game_dir.set(selected)

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            self._append_log(self.t("already_running"))
            return
        try:
            config = self._read_config()
            self._save_settings()
        except Exception as exc:
            messagebox.showerror(self.t("cannot_start"), str(exc))
            return

        self.stop_event = threading.Event()
        self.worker = PublisherThread(config, self.status_queue, self.stop_event)
        self.worker.start()
        self.state_text.set(self.t("running"))
        self.game_text.set(self.t("watching_logs"))
        self.server_text.set(self.t("connecting"))
        self._append_log(self.t("publisher_started"))

    def _stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        self.state_text.set(self.t("stopped"))
        self._append_log(self.t("publisher_stopped"))

    def _test_once(self) -> None:
        try:
            config = self._read_config()
            log_paths = [
                config.game_dir / "Player-prev.log",
                config.game_dir / "Player.log",
            ]
            patch, templates = load_templates(default_cards_cache(config.game_dir))
            visual_resolver = create_visual_resolver(config.visual_fallback)
            state = build_state(
                read_log_text(log_paths),
                templates,
                build_calibration(calibration_args(config)),
                visual_resolver=visual_resolver,
            )
            payload = state.payload(patch)
            preview = {
                "phase": payload.get("phase"),
                "board": [
                    {
                        "slot": item.get("slot"),
                        "id": item.get("id"),
                        "source": item.get("source"),
                        "confidence": item.get("confidence"),
                        "bbox": item.get("bbox"),
                    }
                    for item in payload.get("board", [])
                ],
                "opponentBoard": [
                    {
                        "slot": item.get("slot"),
                        "id": item.get("id"),
                        "source": item.get("source"),
                        "confidence": item.get("confidence"),
                        "bbox": item.get("bbox"),
                    }
                    for item in payload.get("opponentBoard", [])
                ],
            }
            self._append_log(json.dumps(preview, ensure_ascii=False, indent=2))
            self.game_text.set(f"OK, {len(templates)} templates loaded")
        except Exception as exc:
            messagebox.showerror(self.t("test_failed"), str(exc))

    def _drain_status_queue(self) -> None:
        while True:
            try:
                status = self.status_queue.get_nowait()
            except queue.Empty:
                break
            self._apply_status(status)
        self.after(200, self._drain_status_queue)

    def _apply_status(self, status: PublishStatus) -> None:
        self.server_text.set("OK" if status.ok else "Error")
        self.phase_text.set(status.phase)
        self.board_text.set(
            f"{status.board_count}: {', '.join(status.board_names[:6])}"
            if status.board_names
            else str(status.board_count)
        )
        if status.stats:
            pve = max(0, status.stats.combats - status.stats.pvp_combats)
            self.stats_text.set(
                f"Purchases {status.stats.purchases}, sales {status.stats.sales}, "
                f"combat {pve} PvE / {status.stats.pvp_combats} PvP"
            )
        self._append_log(f"seq={status.seq} {status.message}")

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")

    def _on_close(self) -> None:
        self._stop()
        self.destroy()


def smoke_test() -> None:
    SettingsStore(app_config_dir() / "smoke-settings.json")
    validate_server_url(DEFAULT_EBS_URL)
    validate_server_url("http://127.0.0.1:8000")


def main() -> None:
    parser = argparse.ArgumentParser(description="The Bazaar Live Board desktop companion")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
        return
    app = CompanionApp()
    app.mainloop()


if __name__ == "__main__":
    main()