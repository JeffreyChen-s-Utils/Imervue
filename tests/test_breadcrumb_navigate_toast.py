"""Tests for the breadcrumb navigation toast — phase 36c.

Clicking a breadcrumb segment whose path no longer exists used to
silently fail (the helper would just ``return``). It now surfaces a
warning toast, and a true exception inside the navigate path emits
an error toast — both via the main window's ``ToastManager``.
"""
from __future__ import annotations

import pytest

from Imervue.gui.breadcrumb_bar import BreadcrumbBar


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
    """Minimal surface ``BreadcrumbBar`` reads from."""

    def __init__(self):
        self.toast = _ToastSpy()


@pytest.fixture
def bar(qapp):
    main = _StubMainWindow()
    bar = BreadcrumbBar(main)
    yield bar
    bar.deleteLater()


def test_navigate_to_missing_folder_emits_warning(bar, tmp_path):
    ghost = tmp_path / "ghost"
    bar._navigate(str(ghost))   # noqa: SLF001
    msgs = bar._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "warning"
    assert "ghost" in msgs[0][1]


def test_navigate_runtime_failure_emits_error(qapp, tmp_path, monkeypatch):
    """Even though the directory exists, an exception bubbling up from
    ``open_path`` must be surfaced as an error toast rather than buried
    in the log."""
    folder = tmp_path / "real"
    folder.mkdir()

    main = _StubMainWindow()
    # Stand-in for the rest of the main window surface that
    # ``_navigate`` reaches into.
    main.model = type("M", (), {
        "setRootPath": lambda self, *_: None,
        "index": lambda self, *_: None,
    })()
    main.tree = type("T", (), {"setRootIndex": lambda self, *_: None})()

    class _Viewer:
        def clear_tile_grid(self):
            """No-op — the test only asserts on toast, not GL state."""

    main.viewer = _Viewer()

    def fake_open_path(*, main_gui, path):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(
        "Imervue.gpu_image_view.images.image_loader.open_path", fake_open_path,
    )
    bar = BreadcrumbBar(main)
    try:
        bar._navigate(str(folder))   # noqa: SLF001
    finally:
        bar.deleteLater()
    msgs = main.toast.calls
    assert msgs and msgs[0][0] == "error"
    assert "real" in msgs[0][1]
