"""Tests for the breadcrumb navigation toast — phase 36c.

Clicking a breadcrumb segment whose path no longer exists used to
silently fail (the helper would just ``return``). It now surfaces a
warning toast, and a true exception inside the navigate path emits
an error toast — both via the main window's ``ToastManager``.
"""
from __future__ import annotations

import pytest

from Imervue.gui.breadcrumb_bar import BreadcrumbBar
from tests._toast_spy import ToastSpy as _ToastSpy


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


def test_navigate_existing_folder_delegates_to_main_window(qapp, tmp_path):
    """An existing folder is handed to the main window's single navigator
    (which updates the path bar) — the breadcrumb no longer reimplements it."""
    folder = tmp_path / "real"
    folder.mkdir()
    main = _StubMainWindow()
    calls = []
    main.navigate_to_path = calls.append
    bar = BreadcrumbBar(main)
    try:
        bar._navigate(str(folder))   # noqa: SLF001
    finally:
        bar.deleteLater()
    assert calls == [str(folder)]


def test_navigate_runtime_failure_emits_error(qapp, tmp_path):
    """An exception bubbling up from navigation must surface an error toast
    rather than being buried in the log."""
    folder = tmp_path / "real"
    folder.mkdir()
    main = _StubMainWindow()

    def boom(_path):
        raise RuntimeError("decode failed")

    main.navigate_to_path = boom
    bar = BreadcrumbBar(main)
    try:
        bar._navigate(str(folder))   # noqa: SLF001
    finally:
        bar.deleteLater()
    msgs = main.toast.calls
    assert msgs and msgs[0][0] == "error"
    assert "real" in msgs[0][1]
