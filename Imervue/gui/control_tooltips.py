"""Fill missing help across workspaces, late-built dialogs, menus and item views."""
from __future__ import annotations

from html import escape

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMenu, QTabBar, QWidget

from Imervue.gui.control_tooltips_actions import action_tip
from Imervue.gui.control_tooltips_actions import live_call as _live_call
from Imervue.gui.control_tooltips_fields import widget_tip as _widget_tip
from Imervue.gui.control_tooltips_views import refresh_tab_tips, show_viewport_item_tip
from Imervue.gui.tooltip_text import plain_label

_GENERATED = "imervueGeneratedToolTip"


def _store(target, text: str) -> None:
    # Qt may replace toolbar/clear buttons as an action's help changes during a walk.
    if text and shiboken6.isValid(target):
        # Plain text format prevents paths/labels containing '<' from becoming rich text.
        formatted = f"<qt>{escape(text).replace(chr(10), '<br>')}</qt>"
        target.setToolTip(formatted)
        target.setProperty(_GENERATED, formatted)


def ensure_tooltip(target) -> None:
    """Keep authored help; refresh generated help when labels, language or ranges change."""
    _live_call(target, _ensure_tooltip)


def _ensure_tooltip(target) -> None:
    previous = target.property(_GENERATED)
    current = target.toolTip()
    if (current and current != previous
            and (not isinstance(target, QAction)
                 or plain_label(current) != plain_label(target.text()))):
        return
    if isinstance(target, QAction):
        _store(target, action_tip(target))
    elif isinstance(target, QWidget):
        _store(target, _widget_tip(target))


def _tabs_and_menu(widget) -> None:
    _live_call(widget, _update_tabs_and_menu)


def _update_tabs_and_menu(widget) -> None:
    if isinstance(widget, QMenu):
        widget.setToolTipsVisible(True)
        for action in widget.actions():
            ensure_tooltip(action)
    if isinstance(widget, QTabBar):
        refresh_tab_tips(widget)


def fill_missing_tooltips(root: QWidget) -> None:
    """Fill constructed controls including hidden tabs without changing existing tooltips."""
    for widget in [root, *root.findChildren(QWidget)]:
        _tabs_and_menu(widget)
        ensure_tooltip(widget)
    for action in root.findChildren(QAction):
        ensure_tooltip(action)


class _ToolTipFilter(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._handling = False

    def eventFilter(self, watched, event):
        # Qt getters and help updates may synchronously deliver more events.
        # Guard before touching Qt, including event.type(), and let nested
        # events continue through Qt's normal dispatch.
        if self._handling:
            return not shiboken6.isValid(watched)
        self._handling = True
        try:
            handled = _live_call(watched, lambda target: self._handle_event(target, event),
                                 default=True)
            # Qt must not deliver an event to a receiver deleted by a callback.
            return handled or not shiboken6.isValid(watched)
        finally:
            self._handling = False

    def _handle_event(self, watched, event) -> bool:
        event_type = event.type()
        if event_type not in (QEvent.Type.Show, QEvent.Type.ToolTip):
            return False
        if not isinstance(watched, QWidget):
            return False
        if watched.window().windowType() == Qt.WindowType.ToolTip:
            return False
        if event_type == QEvent.Type.Show and isinstance(watched, (QMainWindow, QDialog)):
            fill_missing_tooltips(watched)
        if event_type == QEvent.Type.ToolTip and show_viewport_item_tip(watched, event):
            return True
        _tabs_and_menu(watched)
        ensure_tooltip(watched)
        return False


def install_tooltips(app: QApplication | None) -> None:
    """Install one application-owned help filter; late-created controls need no polling."""
    if app is not None and not hasattr(app, "_imervue_tooltip_filter"):
        handler = _ToolTipFilter(app)
        app.installEventFilter(handler)
        app._imervue_tooltip_filter = handler


def enable_control_tooltips(root: QWidget) -> None:
    """Cover an existing workspace and controls built later in the same application."""
    install_tooltips(QApplication.instance())
    fill_missing_tooltips(root)
