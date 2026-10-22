"""Nested Qt notifications must not recursively inspect tabs or regenerate help."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import shiboken6
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QDialog, QMainWindow, QTabWidget, QWidget

from Imervue.Imervue_main_window import ImervueMainWindow
from Imervue.gui import control_tooltips
from Imervue.paint.paint_workspace import PaintWorkspace


class _EventfulTabs(QTabWidget):
    """Model a Qt getter that synchronously delivers another native notification."""

    def __init__(self, parent):
        super().__init__(parent)
        self.bar = super().tabBar()
        self.getter_calls = 0

    def tabBar(self):  # noqa: N802 - Qt override
        self.getter_calls += 1
        # Bound the old recursion so a regression fails without overflowing Qt.
        if self.getter_calls < 6:
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.sendEvent(self.bar, QEvent(QEvent.Type.User))
        return self.bar


@pytest.fixture(params=[ImervueMainWindow, PaintWorkspace])
def shell(request, qapp):
    class Shell(request.param):
        def __init__(self):
            # Exercise the real filters without unrelated GL/services construction.
            QMainWindow.__init__(self)
            tabs = _EventfulTabs(self)
            self._main_tabs = self._tabs = tabs
            self._workspace_tab_bar = self._canvas_tab_bar = tabs.bar
            self._canvas = QWidget(self)
            self.modify_panel = SimpleNamespace(navigate_image=MagicMock())
            self._navigate_paint_image = MagicMock()
            for name in ("Browse", "Modify", "Paint"):
                tabs.addTab(QWidget(), name)
            tabs.bar.installEventFilter(self)

    window = Shell()
    yield window
    window._tabs.bar.removeEventFilter(window)
    shiboken6.delete(window)


def test_unrelated_notifications_do_not_reenter_tab_getters(shell, qapp):
    qapp.sendEvent(shell._tabs.bar, QEvent(QEvent.Type.User))
    assert shell._tabs.getter_calls == 0


@pytest.mark.parametrize("shell", [ImervueMainWindow], indirect=True)
def test_main_tab_navigation_still_routes_keys_without_tab_getters(shell):
    for index, callback in ((1, shell.modify_panel.navigate_image),
                            (2, shell._navigate_paint_image)):
        shell._tabs.setCurrentIndex(index)
        for key, direction in ((Qt.Key.Key_Left, -1), (Qt.Key.Key_Right, 1)):
            event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
            assert shell.eventFilter(shell._tabs.bar, event)
            callback.assert_called_with(direction)
    assert shell._tabs.getter_calls == 0


@pytest.mark.parametrize("shell", [PaintWorkspace], indirect=True)
def test_paint_middle_click_still_closes_the_target_tab_without_a_getter(shell):
    shell.close_tab = MagicMock()
    position = QPointF(shell._tabs.bar.tabRect(1).center())
    event = QMouseEvent(QEvent.Type.MouseButtonRelease, position, position,
                        Qt.MouseButton.MiddleButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
    assert shell.eventFilter(shell._tabs.bar, event)
    shell.close_tab.assert_called_once_with(1)
    assert shell._tabs.getter_calls == 0


def test_nested_show_during_help_generation_is_not_reprocessed(qapp, monkeypatch):
    control_tooltips.install_tooltips(qapp)
    dialog = QDialog()
    original = control_tooltips.fill_missing_tooltips
    visited = []

    def nested_show(root):
        visited.append(root)
        if len(visited) < 6:
            qapp.sendEvent(root, QEvent(QEvent.Type.Show))
        original(root)

    monkeypatch.setattr(control_tooltips, "fill_missing_tooltips", nested_show)
    try:
        qapp.sendEvent(dialog, QEvent(QEvent.Type.Show))
        assert visited == [dialog]
    finally:
        shiboken6.delete(dialog)


def test_help_guard_recovers_after_an_exception(qapp, monkeypatch):
    handler = control_tooltips._ToolTipFilter()
    dialog = QDialog()
    fill = MagicMock(side_effect=ValueError("help failed"))
    monkeypatch.setattr(control_tooltips, "fill_missing_tooltips", fill)
    try:
        with pytest.raises(ValueError, match="help failed"):
            handler.eventFilter(dialog, QEvent(QEvent.Type.Show))
        fill.side_effect = None
        assert handler.eventFilter(dialog, QEvent(QEvent.Type.Show)) is False
        assert fill.call_count == 2
    finally:
        shiboken6.delete(dialog)
        shiboken6.delete(handler)


def test_help_guard_starts_before_reading_the_native_event_type(qapp, monkeypatch):
    handler = control_tooltips._ToolTipFilter()
    dialog = QDialog()
    fill = MagicMock()
    monkeypatch.setattr(control_tooltips, "fill_missing_tooltips", fill)

    class Event:
        reads = 0

        def type(self):
            self.reads += 1
            if self.reads < 6:
                handler.eventFilter(dialog, self)
            return QEvent.Type.Show

    event = Event()
    try:
        assert handler.eventFilter(dialog, event) is False
        assert event.reads == 1
        fill.assert_called_once_with(dialog)
    finally:
        shiboken6.delete(dialog)
        shiboken6.delete(handler)


def test_help_consumes_an_event_when_its_receiver_is_deleted(qapp, monkeypatch):
    handler = control_tooltips._ToolTipFilter()
    dialog = QDialog()
    replacement = QDialog()
    monkeypatch.setattr(control_tooltips, "fill_missing_tooltips", shiboken6.delete)
    try:
        assert handler.eventFilter(dialog, QEvent(QEvent.Type.Show)) is True
        assert not shiboken6.isValid(dialog)
        fill = MagicMock()
        monkeypatch.setattr(control_tooltips, "fill_missing_tooltips", fill)
        assert handler.eventFilter(replacement, QEvent(QEvent.Type.Show)) is False
        fill.assert_called_once_with(replacement)
    finally:
        if shiboken6.isValid(dialog):
            shiboken6.delete(dialog)
        shiboken6.delete(replacement)
        shiboken6.delete(handler)
