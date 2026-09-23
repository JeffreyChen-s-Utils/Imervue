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
