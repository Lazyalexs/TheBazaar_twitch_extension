from __future__ import annotations

import threading
import ctypes
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageGrab, ImageOps


_VISION_LOG_PATH = None


def _vision_log(msg: str) -> None:
    global _VISION_LOG_PATH
    if _VISION_LOG_PATH is None:
        import tempfile
        _VISION_LOG_PATH = Path(tempfile.gettempdir()) / "thebazaar_vision_debug.log"
    line = f"{__import__('time').strftime('%H:%M:%S')} {msg}\n"
    try:
        with open(_VISION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


IMAGE_SIZE = (32, 32)
DOWNLOAD_WORKERS = 8
USER_AGENT = "TheBazaarLiveBoardCompanion/visual-fallback"


@dataclass(frozen=True)
class ItemArtRef:
    title: str
    size: str
    tier: str | None
    cooldown: float | None
    image_url: str
    cache_key: str
    heroes: tuple[str, ...] = ()   # lowercase, e.g. ('stelle',) or ('common',)


@dataclass(frozen=True)
class ImageSignature:
    phash: int  # 64-bit dHash perceptual fingerprint


@dataclass(frozen=True)
class VisualMatch:
    title: str
    tier: str | None
    cooldown: float | None
    confidence: float
    score: float
    margin: float
    runner_up: str | None = None
    runner_up_score: float | None = None


def default_items_data_path() -> Path | None:
    roots = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path(__file__).resolve().parents[1])

    for root in roots:
        path = root / "extension" / "data" / "items.min.json"
        if path.exists():
            return path
    return None


def default_cache_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return root / "TheBazaarLiveBoard" / "vision-art-cache"


def normalized_size(value: str | None) -> str:
    clean = str(value or "small").strip().lower()
    return clean if clean in {"small", "medium", "large"} else "small"


def load_item_refs(path: Path) -> list[ItemArtRef]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    refs: list[ItemArtRef] = []
    if not isinstance(raw, list):
        return refs

    for item in raw:
        if not isinstance(item, dict) or item.get("type") != "item":
            continue
        title = str(item.get("name") or item.get("id") or "").strip()
        image_url = str(item.get("imageSource") or "").strip()
        if not title or not image_url:
            continue
        cache_key = str(item.get("cardId") or item.get("id") or title)
        cooldown = item.get("cooldown")
        heroes_raw = item.get("heroes") or []
        heroes = tuple(
            str(h).strip().lower()
            for h in heroes_raw
            if isinstance(h, str) and h.strip()
        )
        refs.append(
            ItemArtRef(
                title=title,
                size=normalized_size(str(item.get("size") or "")),
                tier=str(item.get("baseTier")) if item.get("baseTier") else None,
                cooldown=float(cooldown) if isinstance(cooldown, (int, float)) else None,
                image_url=image_url,
                cache_key=cache_key,
                heroes=heroes,
            )
        )
    return refs


def game_window_title(title: str) -> bool:
    lower = title.strip().lower()
    return "the bazaar" in lower and "companion" not in lower


def game_client_rect() -> tuple[int, int, int, int] | None:
    if os.name != "nt":
        return None

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    candidates: list[tuple[int, int, int, int]] = []

    def enum_window(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length <= 0:
            return True

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        if not game_window_title(title_buffer.value):
            return True

        rect = RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True

        point = POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
            return True

        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width >= 640 and height >= 360:
            candidates.append((point.x, point.y, point.x + width, point.y + height))
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(callback(enum_window), 0)
    if not candidates:
        return None
    return max(candidates, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))


def capture_game_window() -> Image.Image | None:
    rect = game_client_rect()
    if rect is None:
        return None
    try:
        return ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")
    except Exception:
        return None


def bbox_crop(image: Image.Image, bbox: dict[str, Any]) -> Image.Image | None:
    width, height = image.size
    try:
        left = max(0, int(float(bbox["x"]) * width))
        top = max(0, int(float(bbox["y"]) * height))
        right = min(width, int((float(bbox["x"]) + float(bbox["w"])) * width))
        bottom = min(height, int((float(bbox["y"]) + float(bbox["h"])) * height))
    except (KeyError, TypeError, ValueError):
        return None

    if right - left < 12 or bottom - top < 12:
        return None
    return image.crop((left, top, right, bottom))


def _resample_filter() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def crop_relative(image: Image.Image, bounds: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left = int(width * bounds[0])
    top = int(height * bounds[1])
    right = int(width * bounds[2])
    bottom = int(height * bounds[3])
    return image.crop((left, top, right, bottom))


def crop_variants(image: Image.Image) -> list[Image.Image]:
    return [
        image,
        crop_relative(image, (0.04, 0.04, 0.96, 0.92)),
        crop_relative(image, (0.08, 0.08, 0.92, 0.84)),
        crop_relative(image, (0.12, 0.00, 0.88, 0.76)),
    ]


def signature(image: Image.Image) -> ImageSignature:
    prepared = ImageOps.exif_transpose(image).convert("RGB")
    fitted = ImageOps.fit(prepared, (9, 8), _resample_filter(), centering=(0.5, 0.45))
    gray = ImageOps.grayscale(fitted)
    pixels = list(gray.getdata())
    bits = 0
    for row in range(8):
        base = row * 9
        for col in range(8):
            left = pixels[base + col]
            right = pixels[base + col + 1]
            if left > right:
                bits |= (1 << (row * 8 + col))
    return ImageSignature(phash=bits)


def signature_distance(left: ImageSignature, right: ImageSignature) -> float:
    """Hamming distance between dHashes, normalized to [0, 1]."""
    return bin(left.phash ^ right.phash).count("1") / 64.0


class VisualCardResolver:
    def __init__(
        self,
        items_data_path: Path | None = None,
        cache_dir: Path | None = None,
        threshold: float = 0.30,
        ambiguity_margin: float = 0.015,
    ) -> None:
        self.items_data_path = items_data_path or default_items_data_path()
        self.cache_dir = cache_dir or default_cache_dir()
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin
        self._refs: list[ItemArtRef] | None = None
        self._ref_signatures: dict[str, ImageSignature | None] = {}
        self._resolved: dict[str, VisualMatch] = {}
        self._screen: Image.Image | None = None
        self._signature_lock = threading.Lock()
        self._prefetch_thread: threading.Thread | None = None
        self._prefetch_started = False
        self._load_signature_cache()

    def begin_frame(self) -> None:
        self._screen = None

    def match(
        self,
        slot: int,
        instance_id: str,
        size: str,
        bbox: dict[str, Any],
        hero: str | None = None,
    ) -> VisualMatch | None:
        if instance_id in self._resolved:
            return self._resolved[instance_id]
        if self.items_data_path is None or not self.items_data_path.exists():
            return None

        if self._screen is None:
            self._screen = capture_game_window()
            if self._screen is None:
                _vision_log("ERROR: capture_game_window returned None - game window not found")
            else:
                _vision_log(f"captured screen {self._screen.size}")
        if self._screen is None:
            return None

        crop = bbox_crop(self._screen, bbox)
        if crop is None:
            return None

        wanted_size = normalized_size(size)
        all_refs = self._load_refs()
        candidates = [ref for ref in all_refs if ref.size == wanted_size]
        if not candidates:
            candidates = all_refs

        # hero filter — keep items for this hero + 'common', fall back if empty
        if hero:
            hero_norm = hero.strip().lower()
            narrowed = [
                ref for ref in candidates
                if hero_norm in ref.heroes or 'common' in ref.heroes
            ]
            if narrowed:
                _vision_log(
                    f"hero={hero_norm}: pool {len(candidates)} -> {len(narrowed)}"
                )
                candidates = narrowed

        target_signatures = [signature(variant) for variant in crop_variants(crop)]
        best_ref: ItemArtRef | None = None
        best_score = 1.0
        second_ref: ItemArtRef | None = None
        second_score = 1.0

        for ref, ref_signature in self._candidate_signatures(candidates):
            if ref_signature is None:
                continue
            score = min(
                signature_distance(target, ref_signature)
                for target in target_signatures
            )
            if score < best_score:
                second_score = best_score
                second_ref = best_ref
                best_score = score
                best_ref = ref
            elif score < second_score:
                second_score = score
                second_ref = ref

        if best_ref is None or best_score > self.threshold:
            _vision_log(f"slot={slot} NO MATCH: best={best_ref.title if best_ref else 'None'} score={best_score:.4f} threshold={self.threshold}")
            return None

        margin = second_score - best_score
        if second_ref is not None and margin < self.ambiguity_margin:
            _vision_log(f"slot={slot} AMBIGUOUS: {best_ref.title} vs {second_ref.title} margin={margin:.4f}")
            return None

        _vision_log(f"slot={slot} MATCH: {best_ref.title} tier={best_ref.tier} score={best_score:.4f} margin={margin:.4f}")

        match = VisualMatch(
            title=best_ref.title,
            tier=best_ref.tier,
            cooldown=best_ref.cooldown,
            confidence=confidence_from_scores(best_score, margin, self.threshold),
            score=round(best_score, 4),
            margin=round(margin, 4),
            runner_up=second_ref.title if second_ref else None,
            runner_up_score=round(second_score, 4) if second_ref else None,
        )
        self._resolved[instance_id] = match
        return match

    def _load_refs(self) -> list[ItemArtRef]:
        if self._refs is None:
            self._refs = load_item_refs(self.items_data_path) if self.items_data_path else []
        return self._refs

    def _signature_cache_path(self) -> Path:
        return self.cache_dir / "_signatures_v2.json"

    def _load_signature_cache(self) -> None:
        """Restore previously-computed signatures from disk (best-effort)."""
        path = self._signature_cache_path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for cache_key, payload in raw.items():
            try:
                if payload is None:
                    with self._signature_lock:
                        self._ref_signatures[cache_key] = None
                    continue
                phash = payload.get("phash")
                if not isinstance(phash, int):
                    continue  # old-format entry, skip; will be regenerated
                with self._signature_lock:
                    self._ref_signatures[cache_key] = ImageSignature(phash=int(phash))
            except (KeyError, TypeError, ValueError):
                continue

    def _save_signature_cache(self) -> None:
        """Persist current _ref_signatures to disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        with self._signature_lock:
            snapshot = dict(self._ref_signatures)
        encoded: dict[str, Any] = {}
        for key, sig in snapshot.items():
            if sig is None:
                encoded[key] = None
            else:
                encoded[key] = {"phash": sig.phash}
        tmp = self._signature_cache_path().with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(encoded), encoding="utf-8")
            os.replace(tmp, self._signature_cache_path())
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _run_prefetch(self) -> None:
        try:
            refs = self._load_refs()
            # split into chunks to allow other threads to interleave
            with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
                futures = {
                    executor.submit(self._signature_for_ref, ref): ref
                    for ref in refs
                    if ref.cache_key not in self._ref_signatures  # skip already loaded from disk
                }
                for future in as_completed(futures):
                    ref = futures[future]
                    try:
                        signature_result = future.result()
                    except Exception:
                        signature_result = None
                    with self._signature_lock:
                        self._ref_signatures[ref.cache_key] = signature_result
            self._save_signature_cache()
            _vision_log(f"prefetch complete: {len(self._ref_signatures)} signatures cached")
        except Exception as exc:
            _vision_log(f"prefetch error: {exc!r}")

    def _ensure_prefetch_started(self) -> None:
        if self._prefetch_started:
            return
        self._prefetch_started = True
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._prefetch_thread = threading.Thread(
            target=self._run_prefetch,
            name="VisualCardResolver-prefetch",
            daemon=True,
        )
        self._prefetch_thread.start()
        _vision_log("prefetch thread started")

    def _candidate_signatures(
        self,
        candidates: list[ItemArtRef],
    ) -> list[tuple[ItemArtRef, ImageSignature | None]]:
        self._ensure_prefetch_started()
        with self._signature_lock:
            return [
                (ref, self._ref_signatures.get(ref.cache_key))
                for ref in candidates
            ]

    def _signature_for_ref(self, ref: ItemArtRef) -> ImageSignature | None:
        path = self._cache_path(ref)
        try:
            if not path.exists():
                request = urllib.request.Request(
                    ref.image_url,
                    headers={"User-Agent": USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    path.write_bytes(response.read())
            image = Image.open(io.BytesIO(path.read_bytes()))
            return signature(image)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError):
            return None

    def _cache_path(self, ref: ItemArtRef) -> Path:
        digest = hashlib.sha1(ref.image_url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.img"


def confidence_from_scores(score: float, margin: float, threshold: float) -> float:
    threshold_room = max(0.0, min(1.0, 1.0 - (score / max(threshold, 0.0001))))
    margin_room = max(0.0, min(1.0, margin / 0.06))  # 0.06 = ~4 bit advantage = strong
    return round(0.82 + (threshold_room * 0.1) + (margin_room * 0.08), 2)
