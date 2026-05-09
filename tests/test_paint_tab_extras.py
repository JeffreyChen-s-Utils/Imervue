"""Tests for tab middle-click close + hover tooltip."""
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
# Middle-click close routing
# ---------------------------------------------------------------------------


def test_handle_tab_bar_event_routes_middle_click_to_close(workspace):
    """A middle-click release at a valid tab index must trigger
    ``close_tab`` for that index. The handler returns ``True`` so
    Qt drops the event instead of also activating the tab."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    workspace.new_tab()
    closed_indices = []
    original_close = workspace.close_tab
    workspace.close_tab = lambda index, **kw: (
        closed_indices.append(index) or original_close(index, **kw)
    )
    rect = workspace._tabs.tabBar().tabRect(0)  # noqa: SLF001
    pos = QPointF(rect.center())
    evt = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        pos, pos,
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    consumed = workspace._handle_tab_bar_event(evt)  # noqa: SLF001
    assert consumed is True
    assert closed_indices == [0]


def test_handle_tab_bar_event_ignores_left_click(workspace):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    rect = workspace._tabs.tabBar().tabRect(0)  # noqa: SLF001
    pos = QPointF(rect.center())
    evt = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        pos, pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert workspace._handle_tab_bar_event(evt) is False  # noqa: SLF001


def test_handle_tab_bar_event_ignores_press(workspace):
    """The handler waits for ``MouseButtonRelease`` so Qt's own tab
    drag-detect machinery on press isn't disturbed."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    rect = workspace._tabs.tabBar().tabRect(0)  # noqa: SLF001
    pos = QPointF(rect.center())
    evt = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos, pos,
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert workspace._handle_tab_bar_event(evt) is False  # noqa: SLF001


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------


def test_tab_tooltip_includes_size(workspace):
    """The hover tooltip surfaces the canvas dimensions so the user
    can identify a tab whose title got truncated by Qt's tab bar."""
    workspace._refresh_tab_title(workspace.canvas())  # noqa: SLF001
    tip = workspace._tabs.tabToolTip(0)  # noqa: SLF001
    h, w = workspace.canvas().document().shape
    assert f"{w}×{h}" in tip


def test_tab_tooltip_marks_modified_state(workspace):
    workspace._on_dispatcher_commit()  # noqa: SLF001
    tip = workspace._tabs.tabToolTip(0)  # noqa: SLF001
    assert "Modified" in tip or "未存" in tip
