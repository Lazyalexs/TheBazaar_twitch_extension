"""Tests for companion.secure_store — SettingsStore atomic save (P0-2)."""

from __future__ import annotations

import json
import os
import pathlib
from unittest import mock

import pytest

from companion.secure_store import SettingsStore


def test_load_returns_empty_on_corrupt_json(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text("not json {{{", encoding="utf-8")
    assert SettingsStore(p).load() == {}


def test_save_does_not_leave_tmp_file(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    SettingsStore(p).save({"language": "ru"})
    assert not p.with_suffix(p.suffix + ".tmp").exists()


def test_save_contents_are_roundtripped(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    SettingsStore(p).save({"language": "ru", "theme": "dark"})
    assert SettingsStore(p).load() == {"language": "ru", "theme": "dark"}


def test_save_none_value_filtered(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    SettingsStore(p).save({"language": "ru", "theme": None})
    loaded = SettingsStore(p).load()
    assert "theme" not in loaded
    assert loaded["language"] == "ru"


def test_save_no_token_means_no_tokenDpapi_key(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    SettingsStore(p).save({"language": "ru"})
    assert "tokenDpapi" not in json.loads(p.read_text(encoding="utf-8"))


def test_save_uses_atomic_replace(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    real_replace = os.replace
    calls: list[tuple[str, str]] = []

    def spy(src: str, dst: str) -> None:
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    with mock.patch("os.replace", side_effect=spy):
        SettingsStore(p).save({"key": "val"})

    assert len(calls) == 1
    src, dst = calls[0]
    assert src.endswith(".json.tmp")
    assert dst.endswith("settings.json")


def test_save_cleans_up_tmp_on_replace_failure(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "settings.json"
    tmp = p.with_suffix(p.suffix + ".tmp")

    with mock.patch("os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError, match="boom"):
            SettingsStore(p).save({"key": "val"})

    assert not tmp.exists()
