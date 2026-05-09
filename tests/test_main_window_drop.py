"""Tests for the main window's drag-and-drop coverage — Phase 34c.

Focuses on the predicate (``_is_supported_drop``) and the dispatch
(``_open_dropped_path``) rather than the QDropEvent plumbing, which
needs a live X server / Wayland session to actually fire.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Imervue.Imervue_main_window import ImervueMainWindow


# ---------------------------------------------------------------------------
# _is_supported_drop — pure predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", [
    ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp",
    ".gif", ".cr2", ".nef", ".arw", ".dng",
])
def test_supported_drop_accepts_image_extensions(tmp_path: Path, ext: str):
    fake = tmp_path / f"x{ext}"
    fake.write_bytes(b"")
    assert ImervueMainWindow._is_supported_drop(str(fake))


@pytest.mark.parametrize("ext", [".txt", ".mp3", ".pdf", ".exe"])
def test_supported_drop_rejects_other_extensions(tmp_path: Path, ext: str):
    fake = tmp_path / f"x{ext}"
    fake.write_bytes(b"")
    assert not ImervueMainWindow._is_supported_drop(str(fake))


def test_supported_drop_accepts_directory(tmp_path: Path):
    folder = tmp_path / "snaps"
    folder.mkdir()
    assert ImervueMainWindow._is_supported_drop(str(folder))


def test_supported_drop_extension_is_case_insensitive(tmp_path: Path):
    fake = tmp_path / "PHOTO.JPG"
    fake.write_bytes(b"")
    assert ImervueMainWindow._is_supported_drop(str(fake))


# ---------------------------------------------------------------------------
# _open_dropped_path — dispatch logic via stubbed surfaces
# ---------------------------------------------------------------------------


class _FakeViewer:
    """Stand-in for ``GPUImageView`` so we don't need GL."""


class _ToastSpy:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, text, duration_ms=2500):
        self.calls.append(("info", text))

    def success(self, text, duration_ms=2500):
        self.calls.append(("success", text))

    def warning(self, text, duration_ms=4000):
        self.calls.append(("warning", text))

    def error(self, text, duration_ms=4000):
        self.calls.append(("error", text))


class _StubMainWindow:
    """Bare attribute surface needed by ``_open_dropped_path`` — bound
    to the production method so we exercise the real dispatch."""

    def __init__(self):
        self.viewer = _FakeViewer()
        self.toast = _ToastSpy()
        self._open_startup_folder_calls: list[str] = []

    def _open_startup_folder(self, folder: str):
        self._open_startup_folder_calls.append(folder)

    _open_dropped_path = ImervueMainWindow._open_dropped_path


def test_open_dropped_folder_routes_to_open_startup_folder(qapp, tmp_path):
    main = _StubMainWindow()
    main._open_dropped_path(str(tmp_path))   # noqa: SLF001
    assert main._open_startup_folder_calls == [str(tmp_path)]   # noqa: SLF001
    assert main.toast.calls == []


def test_open_dropped_image_calls_open_path(qapp, tmp_path, monkeypatch):
    src = tmp_path / "shot.png"
    src.write_bytes(b"")
    main = _StubMainWindow()
    captured = {}

    def fake_open_path(*, main_gui, path):
        captured["main_gui"] = main_gui
        captured["path"] = path

    monkeypatch.setattr(
        "Imervue.Imervue_main_window.open_path", fake_open_path,
    )
    main._open_dropped_path(str(src))   # noqa: SLF001
    assert captured["path"] == str(src)
    assert captured["main_gui"] is main.viewer
    assert main.toast.calls == []


def test_open_dropped_image_failure_surfaces_toast(qapp, tmp_path, monkeypatch):
    src = tmp_path / "broken.png"
    src.write_bytes(b"")
    main = _StubMainWindow()

    def fake_open_path(*, main_gui, path):
        raise RuntimeError("decoder boom")

    monkeypatch.setattr(
        "Imervue.Imervue_main_window.open_path", fake_open_path,
    )
    main._open_dropped_path(str(src))   # noqa: SLF001
    assert main.toast.calls and main.toast.calls[0][0] == "error"
    assert "broken.png" in main.toast.calls[0][1]


def test_open_dropped_path_silent_for_missing_file(qapp, tmp_path, monkeypatch):
    """A path that doesn't exist on disk is not a folder OR a file —
    the dispatch should bail out without raising."""
    main = _StubMainWindow()
    monkeypatch.setattr(
        "Imervue.Imervue_main_window.open_path",
        lambda **_: pytest.fail("open_path should not run for missing files"),
    )
    main._open_dropped_path(str(tmp_path / "ghost.png"))   # noqa: SLF001
    assert main._open_startup_folder_calls == []   # noqa: SLF001
