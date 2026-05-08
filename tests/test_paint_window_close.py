"""Tests for window-level close protection on unsaved tabs."""
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


def _close_event():
    """Return a real ``QCloseEvent`` — needed because ``QMainWindow.
    closeEvent`` calls ``super().closeEvent`` which insists on the
    actual Qt type. Tests inspect ``event.isAccepted()`` after the
    workspace handler returns to see whether the close went through.
    """
    from PySide6.QtGui import QCloseEvent
    return QCloseEvent()


def test_has_unsaved_tabs_false_on_clean_workspace(workspace):
    assert workspace._has_unsaved_tabs() is False  # noqa: SLF001


def test_has_unsaved_tabs_true_after_dispatcher_commit(workspace):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    assert workspace._has_unsaved_tabs() is True  # noqa: SLF001


def test_unsaved_tab_titles_strips_asterisk(workspace):
    """The list returned to the close prompt shouldn't carry the
    " *" suffix — that's a presentational detail."""
    workspace._on_dispatcher_commit()  # noqa: SLF001
    titles = workspace._unsaved_tab_titles()  # noqa: SLF001
    assert titles
    for title in titles:
        assert "*" not in title


def test_close_with_clean_tabs_proceeds_silently(workspace, monkeypatch):
    confirmed = []
    monkeypatch.setattr(
        workspace, "_confirm_discard_all_unsaved",
        lambda: confirmed.append(True) or True,
    )
    evt = _close_event()
    workspace.closeEvent(evt)
    assert confirmed == []
    assert evt.isAccepted() is True


def test_close_with_dirty_tab_invokes_confirm(workspace, monkeypatch):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    asked = []
    monkeypatch.setattr(
        workspace, "_confirm_discard_all_unsaved",
        lambda: asked.append(True) or True,
    )
    evt = _close_event()
    workspace.closeEvent(evt)
    assert asked == [True]


def test_close_cancelled_blocks_event(workspace, monkeypatch):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    monkeypatch.setattr(
        workspace, "_confirm_discard_all_unsaved", lambda: False,
    )
    evt = _close_event()
    workspace.closeEvent(evt)
    assert evt.isAccepted() is False


def test_close_discarded_proceeds(workspace, monkeypatch):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    monkeypatch.setattr(
        workspace, "_confirm_discard_all_unsaved", lambda: True,
    )
    evt = _close_event()
    workspace.closeEvent(evt)
    assert evt.isAccepted() is True
