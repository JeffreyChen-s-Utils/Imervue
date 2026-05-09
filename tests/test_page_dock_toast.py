"""Tests for the PageDock's toast routing — Phase 34g.

When the artist tries to add a page without an open project, the dock
used to throw a modal QMessageBox.information. Now it prefers the
workspace's ToastManager (non-blocking) and only falls back to the
modal when no toast surface is reachable.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from Imervue.paint.page_dock import PageDock


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


class _StubWorkspace(QWidget):
    """Owns a ``.toast`` exactly like the real PaintWorkspace."""

    def __init__(self):
        super().__init__()
        self.toast = _ToastSpy()


@pytest.fixture
def workspace_with_toast(qapp):
    ws = _StubWorkspace()
    yield ws
    ws.deleteLater()


def test_warn_no_project_uses_workspace_toast(qapp, workspace_with_toast):
    dock = PageDock(workspace_with_toast, parent=workspace_with_toast)
    try:
        dock._warn_no_project()   # noqa: SLF001
        assert workspace_with_toast.toast.calls
        severity, text = workspace_with_toast.toast.calls[0]
        assert severity == "info"
        # The message contains the actionable fallback hint so the
        # artist knows where to start a new project.
        assert "New Project" in text or "project" in text.lower()
    finally:
        dock.deleteLater()


def test_warn_no_project_falls_back_to_messagebox_without_toast(
    qapp, monkeypatch,
):
    """A dock parented under a bare widget (no toast) should still
    surface the warning via QMessageBox."""
    bare_parent = QWidget()
    captured: list[tuple[str, str]] = []

    def fake_information(parent, title, body):
        captured.append((title, body))

    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", fake_information)
    dock = PageDock(lambda: None, parent=bare_parent)
    try:
        dock._warn_no_project()   # noqa: SLF001
        assert captured
        # The fallback body matches what the toast path emits.
        assert "project" in captured[0][1].lower()
    finally:
        dock.deleteLater()
        bare_parent.deleteLater()


def test_find_toast_walks_parent_chain(qapp, workspace_with_toast):
    """The dock can be embedded under an extra container widget — the
    toast lookup must walk up the parent chain until it finds the
    workspace's manager."""
    intermediate = QWidget(workspace_with_toast)
    dock = PageDock(workspace_with_toast, parent=intermediate)
    try:
        toast = dock._find_toast()   # noqa: SLF001
        assert toast is workspace_with_toast.toast
    finally:
        dock.deleteLater()
        intermediate.deleteLater()
