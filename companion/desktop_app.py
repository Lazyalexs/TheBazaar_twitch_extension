from __future__ import annotations

import argparse
import json
import queue
import threading
import time
import tkinter as tk
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace
from typing import Any

from companion.log_companion import (
    build_calibration,
    build_snapshot,
    build_state,
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
DEFAULT_CHANNEL_ID = "274185831"


@dataclass(frozen=True)
class AppConfig:
    ebs_url: str
    channel_id: str
    token: str
    game_dir: Path
    stream_resolution: str
    box_profile: str
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


def calibration_args(config: AppConfig) -> SimpleNamespace:
    return SimpleNamespace(
        stream_resolution=config.stream_resolution,
        stream_width=None,
        stream_height=None,
        disable_window_detect=False,
        box_profile=config.box_profile,
        board_x=0.09,
        board_y=0.52,
        socket_step=0.075,
        small_width=0.105,
        box_height=0.2,
        pad_x=0.018,
        pad_y=0.005,
        board_left_px=None,
        board_top_px=None,
        socket_step_px=None,
        socket_9_left_px=None,
        small_width_px=None,
        box_height_px=None,
        pad_x_px=None,
        pad_y_px=None,
    )


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
            log_paths = [
                self.config.game_dir / "Player-prev.log",
                self.config.game_dir / "Player.log",
            ]
            seq = 1
            run_id = f"desktop-companion-{int(time.time())}"
            last_payload: bytes | None = None
            last_sent_at = 0.0
            self.output.put(
                PublishStatus(
                    ok=True,
                    message=f"Loaded patch {patch}, {len(templates)} item templates",
                    seq=0,
                    phase="starting",
                    board_count=0,
                    board_names=[],
                    stats=None,
                )
            )

            while not self.stop_event.is_set():
                log_text = read_log_text(log_paths)
                stats = summarize_log_text(log_text)
                state = build_state(log_text, templates, calibration)
                payload = state.payload(patch)
                payload_key = compact_json(payload)
                now = time.monotonic()
                should_send = (
                    payload_key != last_payload
                    or now - last_sent_at >= self.config.max_send_interval
                )

                if should_send:
                    board_names = [str(item["id"]) for item in payload.get("board", [])]
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
        self.title("The Bazaar Live Board Companion")
        self.geometry("920x680")
        self.minsize(780, 560)

        self.store = SettingsStore()
        self.status_queue: queue.Queue[PublishStatus] = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.worker: PublisherThread | None = None

        self.ebs_url = tk.StringVar(value=DEFAULT_EBS_URL)
        self.channel_id = tk.StringVar(value=DEFAULT_CHANNEL_ID)
        self.token = tk.StringVar(value="")
        self.game_dir = tk.StringVar(value=str(default_game_dir()))
        self.stream_resolution = tk.StringVar(value="auto")
        self.box_profile = tk.StringVar(value="1080p")
        self.state_text = tk.StringVar(value="Stopped")
        self.server_text = tk.StringVar(value="Not connected")
        self.game_text = tk.StringVar(value="Not checked")
        self.phase_text = tk.StringVar(value="-")
        self.board_text = tk.StringVar(value="-")
        self.stats_text = tk.StringVar(value="-")

        self._configure_style()
        self._build_ui()
        self._load_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._drain_status_queue)

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
        ttk.Label(header, text="The Bazaar Live Board", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            textvariable=self.state_text,
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        settings = ttk.LabelFrame(root, text="Connection")
        settings.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        settings.columnconfigure(1, weight=1)
        self._field(settings, 0, "EBS URL", self.ebs_url)
        self._field(settings, 1, "Channel ID", self.channel_id)
        self._field(settings, 2, "Companion Token", self.token, show="*")

        ttk.Label(settings, text="Game Folder").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        game_row = ttk.Frame(settings)
        game_row.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
        game_row.columnconfigure(0, weight=1)
        ttk.Entry(game_row, textvariable=self.game_dir).grid(row=0, column=0, sticky="ew")
        ttk.Button(game_row, text="Browse", command=self._browse_game_dir).grid(row=0, column=1, padx=(8, 0))

        options = ttk.LabelFrame(root, text="Stream")
        options.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        options.columnconfigure(1, weight=1)
        self._combo(options, 0, "Resolution", self.stream_resolution, ["auto", "1920x1080", "1280x720"])
        self._combo(options, 1, "Box Profile", self.box_profile, ["1080p", "720p", "normalized"])

        ttk.Label(
            options,
            text="Token хранится через Windows DPAPI. HTTP разрешен только для localhost.",
            wraplength=360,
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))

        live = ttk.LabelFrame(root, text="Live Status")
        live.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        live.columnconfigure(1, weight=1)
        self._status_row(live, 0, "Server", self.server_text)
        self._status_row(live, 1, "Game", self.game_text)
        self._status_row(live, 2, "Phase", self.phase_text)
        self._status_row(live, 3, "Board", self.board_text)
        self._status_row(live, 4, "Stats", self.stats_text)

        actions = ttk.Frame(live)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=12)
        ttk.Button(actions, text="Save", command=self._save_settings).pack(side="left")
        ttk.Button(actions, text="Start", command=self._start).pack(side="left", padx=8)
        ttk.Button(actions, text="Stop", command=self._stop).pack(side="left")
        ttk.Button(actions, text="Test Once", command=self._test_once).pack(side="left", padx=8)

        diagnostics = ttk.LabelFrame(root, text="Diagnostics")
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
        self._append_log(f"Config: {self.store.path}")

    def _field(
        self,
        parent: ttk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        ttk.Entry(parent, textvariable=variable, show=show).grid(row=row, column=1, sticky="ew", padx=10, pady=6)

    def _combo(
        self,
        parent: ttk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row,
            column=1,
            sticky="ew",
            padx=10,
            pady=6,
        )

    def _status_row(self, parent: ttk.Widget, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=row, column=0, sticky="nw", padx=10, pady=7)
        ttk.Label(parent, textvariable=variable, wraplength=370).grid(row=row, column=1, sticky="ew", padx=10, pady=7)

    def _load_settings(self) -> None:
        data = self.store.load()
        self.ebs_url.set(str(data.get("ebsUrl") or DEFAULT_EBS_URL))
        self.channel_id.set(str(data.get("channelId") or DEFAULT_CHANNEL_ID))
        self.token.set(str(data.get("token") or ""))
        self.game_dir.set(str(data.get("gameDir") or default_game_dir()))
        self.stream_resolution.set(str(data.get("streamResolution") or "auto"))
        self.box_profile.set(str(data.get("boxProfile") or "1080p"))
        self._append_log("Settings loaded")

    def _save_settings(self) -> None:
        try:
            config = self._read_config()
            self.store.save(
                {
                    "ebsUrl": config.ebs_url,
                    "channelId": config.channel_id,
                    "token": config.token,
                    "gameDir": str(config.game_dir),
                    "streamResolution": config.stream_resolution,
                    "boxProfile": config.box_profile,
                }
            )
            self._append_log("Settings saved securely")
        except SecureStoreError as exc:
            messagebox.showerror("Secure storage", str(exc))
        except Exception as exc:
            messagebox.showerror("Settings", str(exc))

    def _read_config(self) -> AppConfig:
        ebs_url = validate_server_url(self.ebs_url.get())
        channel_id = self.channel_id.get().strip()
        token = self.token.get().strip()
        game_dir = Path(self.game_dir.get()).expanduser()
        if not channel_id:
            raise ValueError("Channel ID is required")
        if not token:
            raise ValueError("Companion Token is required")
        if not game_dir.exists():
            raise ValueError(f"Game folder not found: {game_dir}")
        if not default_cards_cache(game_dir).exists():
            raise ValueError(f"cards.json not found: {default_cards_cache(game_dir)}")
        return AppConfig(
            ebs_url=ebs_url,
            channel_id=channel_id,
            token=token,
            game_dir=game_dir,
            stream_resolution=self.stream_resolution.get().strip() or "auto",
            box_profile=self.box_profile.get().strip() or "1080p",
            interval=1.1,
            max_send_interval=15.0,
        )

    def _browse_game_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.game_dir.get())
        if selected:
            self.game_dir.set(selected)

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            self._append_log("Already running")
            return
        try:
            config = self._read_config()
            self._save_settings()
        except Exception as exc:
            messagebox.showerror("Cannot start", str(exc))
            return

        self.stop_event = threading.Event()
        self.worker = PublisherThread(config, self.status_queue, self.stop_event)
        self.worker.start()
        self.state_text.set("Running")
        self.game_text.set("Watching logs")
        self.server_text.set("Connecting")
        self._append_log("Publisher started")

    def _stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        self.state_text.set("Stopped")
        self._append_log("Publisher stopped")

    def _test_once(self) -> None:
        try:
            config = self._read_config()
            log_paths = [
                config.game_dir / "Player-prev.log",
                config.game_dir / "Player.log",
            ]
            patch, templates = load_templates(default_cards_cache(config.game_dir))
            state = build_state(
                read_log_text(log_paths),
                templates,
                build_calibration(calibration_args(config)),
            )
            payload = state.payload(patch)
            preview = {
                "phase": payload.get("phase"),
                "board": [item.get("id") for item in payload.get("board", [])],
            }
            self._append_log(json.dumps(preview, ensure_ascii=False, indent=2))
            self.game_text.set(f"OK, {len(templates)} templates loaded")
        except Exception as exc:
            messagebox.showerror("Test failed", str(exc))

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
