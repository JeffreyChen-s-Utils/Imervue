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
from tests._toast_spy import ToastSpy as _ToastSpy


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


# ---------------------------------------------------------------------------
# Inline-rename trigger configuration — phase 36j
# ---------------------------------------------------------------------------


def test_page_list_supports_f2_inline_rename(qapp, workspace_with_toast):
    """The page list must accept F2 (EditKeyPressed) as the trigger
    for inline rename so the gesture matches the file-tree convention.

    Selected-click is also enabled so a slow second click on the
    already-active row enters edit mode — Windows Explorer parity.
    """
    from PySide6.QtWidgets import QAbstractItemView

    dock = PageDock(workspace_with_toast, parent=workspace_with_toast)
    try:
        triggers = dock._list.editTriggers()    # noqa: SLF001
        assert triggers & QAbstractItemView.EditTrigger.EditKeyPressed
        assert triggers & QAbstractItemView.EditTrigger.SelectedClicked
        # Editing must NOT fire on a simple double-click — that gesture
        # is reserved for "switch to this page".
        assert not (triggers & QAbstractItemView.EditTrigger.DoubleClicked)
    finally:
        dock.deleteLater()
