from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any


APP_DIR_NAME = "TheBazaarLiveBoard"
DPAPI_ENTROPY = b"TheBazaarLiveBoard.Companion.v1"


def app_config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME}"


class SecureStoreError(RuntimeError):
    pass


class DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _make_blob(data: bytes) -> tuple[DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    blob = DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def _require_windows() -> None:
    if os.name != "nt":
        raise SecureStoreError("Windows DPAPI is required for secure token storage")


def protect_text(value: str) -> str:
    _require_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    data_blob, data_buffer = _make_blob(value.encode("utf-8"))
    entropy_blob, entropy_buffer = _make_blob(DPAPI_ENTROPY)
    output_blob = DataBlob()

    ok = crypt32.CryptProtectData(
        ctypes.byref(data_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    _ = (data_buffer, entropy_buffer)
    if not ok:
        raise SecureStoreError("CryptProtectData failed")

    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel32.LocalFree(output_blob.pbData)


def unprotect_text(value: str) -> str:
    _require_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    encrypted = base64.b64decode(value.encode("ascii"))
    data_blob, data_buffer = _make_blob(encrypted)
    entropy_blob, entropy_buffer = _make_blob(DPAPI_ENTROPY)
    output_blob = DataBlob()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(data_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    _ = (data_buffer, entropy_buffer)
    if not ok:
        raise SecureStoreError("CryptUnprotectData failed")

    try:
        decrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return decrypted.decode("utf-8")
    finally:
        kernel32.LocalFree(output_blob.pbData)


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_config_dir() / "settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        if not isinstance(data, dict):
            return {}

        token_blob = data.pop("tokenDpapi", "")
        if isinstance(token_blob, str) and token_blob:
            try:
                data["token"] = unprotect_text(token_blob)
            except SecureStoreError:
                data["token"] = ""
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        clean = {
            key: value
            for key, value in data.items()
            if key != "token" and value is not None
        }
        token = str(data.get("token") or "")
        if token:
            clean["tokenDpapi"] = protect_text(token)
        content = json.dumps(clean, ensure_ascii=False, indent=2)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
