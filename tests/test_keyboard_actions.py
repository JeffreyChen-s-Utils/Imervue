"""Tests for ``keyboard_actions._send_to_trash``'s fallback when send2trash is missing."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from Imervue.gpu_image_view.actions import keyboard_actions as mod


@pytest.fixture
def linux_fallback(monkeypatch, tmp_path):
    """No send2trash, a Linux platform and a home directory under tmp_path."""
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(sys, "platform", "linux")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home / ".local" / "share" / "Trash"


def test_moves_the_file_and_writes_trashinfo(linux_fallback, tmp_path):
    victim = tmp_path / "photo.png"
    victim.write_bytes(b"x")
    assert mod._send_to_trash(str(victim)) is True  # noqa: SLF001
    assert not victim.exists()
    assert (linux_fallback / "files" / "photo.png").read_bytes() == b"x"
    info = (linux_fallback / "info" / "photo.png.trashinfo").read_text(encoding="utf-8")
    assert f"Path={victim}" in info


def test_filesystem_failure_returns_false(linux_fallback, tmp_path):
    assert mod._send_to_trash(str(tmp_path / "missing.png")) is False  # noqa: SLF001


def test_unexpected_error_propagates(linux_fallback, tmp_path, monkeypatch):
    import shutil

    def boom(*_a):
        raise RuntimeError("bug")

    victim = tmp_path / "photo.png"
    victim.write_bytes(b"x")
    monkeypatch.setattr(shutil, "move", boom)
    with pytest.raises(RuntimeError):
        mod._send_to_trash(str(victim))  # noqa: SLF001


def test_same_name_trashed_repeatedly_keeps_every_copy(linux_fallback, tmp_path):
    """A timestamp suffix let the third copy within one second overwrite the second."""
    for content in (b"first", b"second", b"third"):
        folder = tmp_path / content.decode()
        folder.mkdir()
        victim = folder / "photo.png"
        victim.write_bytes(content)
        assert mod._send_to_trash(str(victim)) is True  # noqa: SLF001
    files = linux_fallback / "files"
    assert (files / "photo.png").read_bytes() == b"first"
    assert (files / "photo_1.png").read_bytes() == b"second"
    assert (files / "photo_2.png").read_bytes() == b"third"
    assert (linux_fallback / "info" / "photo_1.png.trashinfo").is_file()


def test_free_trash_name_skips_names_with_a_stale_trashinfo(tmp_path):
    files, info = tmp_path / "files", tmp_path / "info"
    files.mkdir()
    info.mkdir()
    (info / "a.png.trashinfo").write_text("", encoding="utf-8")
    (files / "a_1.png").write_bytes(b"")
    assert mod._free_trash_name(files, "a.png", info) == files / "a_2.png"  # noqa: SLF001
    assert mod._free_trash_name(files, "a.png") == files / "a.png"  # noqa: SLF001


def test_macos_fallback_keeps_both(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "send2trash", None)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    for content in (b"first", b"second"):
        folder = tmp_path / content.decode()
        folder.mkdir()
        (folder / "photo.png").write_bytes(content)
        assert mod._send_to_trash(str(folder / "photo.png")) is True  # noqa: SLF001
    trash = tmp_path / "home" / ".Trash"
    assert sorted(p.name for p in trash.iterdir()) == ["photo.png", "photo_1.png"]
