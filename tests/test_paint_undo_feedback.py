"""Tests for the undo / redo non-blocking visual feedback."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


# ---------------------------------------------------------------------------
# Successful undo / redo paths emit info toasts with the remaining depth
# ---------------------------------------------------------------------------


def test_successful_undo_emits_info_toast(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info", lambda text, **k: received.append(text),
    )
    # Stage a snapshot the undo can pop. Mutate the active layer so
    # the next commit captures a non-trivial baseline.
    layer = workspace.canvas().document().active_layer()
    layer.image[0, 0] = (10, 20, 30, 255)
    workspace._on_dispatcher_commit()  # noqa: SLF001
    layer.image[0, 0] = (40, 50, 60, 255)
    workspace.undo()
    assert received
    assert "undo" in received[0].lower() or "復原" in received[0]


def test_successful_redo_emits_info_toast(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info", lambda text, **k: received.append(text),
    )
    layer = workspace.canvas().document().active_layer()
    layer.image[0, 0] = (10, 20, 30, 255)
    workspace._on_dispatcher_commit()  # noqa: SLF001
    layer.image[0, 0] = (40, 50, 60, 255)
    workspace.undo()
    workspace.redo()
    # Last toast was the redo confirmation.
    assert any("redo" in t.lower() or "重做" in t for t in received)


def test_undo_message_includes_remaining_depth(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "info", lambda text, **k: received.append(text),
    )
    # Stage two commits so undo leaves a non-zero remaining depth.
    layer = workspace.canvas().document().active_layer()
    layer.image[0, 0] = (1, 1, 1, 255)
    workspace._on_dispatcher_commit()  # noqa: SLF001
    layer.image[0, 0] = (2, 2, 2, 255)
    workspace._on_dispatcher_commit()  # noqa: SLF001
    layer.image[0, 0] = (3, 3, 3, 255)
    workspace.undo()
    # Some digit appears — proxy for "depth segment present".
    assert any(any(c.isdigit() for c in t) for t in received)


# ---------------------------------------------------------------------------
# Empty stack — warning toast (or fallback)
# ---------------------------------------------------------------------------


def test_undo_with_empty_stack_emits_warning(workspace, monkeypatch):
    """Hitting Ctrl+Z with nothing to undo must produce a visible
    nudge so the user knows the binding is wired but there's
    nothing left."""
    received = []
    monkeypatch.setattr(
        workspace.toast, "warning", lambda text, **k: received.append(text),
    )
    workspace.undo()
    assert received


def test_redo_with_empty_stack_emits_warning(workspace, monkeypatch):
    received = []
    monkeypatch.setattr(
        workspace.toast, "warning", lambda text, **k: received.append(text),
    )
    workspace.redo()
    assert received


# ---------------------------------------------------------------------------
# Fallback path when toast isn't wired
# ---------------------------------------------------------------------------


def test_history_msg_falls_back_to_status_bar_without_toast(workspace):
    """Removing the toast attribute (legacy embedder simulation)
    routes the message through the status bar instead of dropping
    it on the floor."""
    workspace.toast = None
    workspace._broadcast_history_msg("hello", level="info")  # noqa: SLF001
    assert "hello" in workspace._status.currentMessage()  # noqa: SLF001
