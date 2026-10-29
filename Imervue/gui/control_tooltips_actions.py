"""Help text for actions and buttons, plus the guard that skips deleted Qt objects."""
from __future__ import annotations

import shiboken6
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QAbstractButton, QLineEdit, QMenu, QRadioButton, QTabBar, QToolButton

from Imervue.gui.tooltip_text import control_label, existing_description, plain_label, word


def live_call(target, callback, *, default=None):
    """Skip Qt objects deleted during callbacks; propagate errors on live objects."""
    if not shiboken6.isValid(target):
        return default
    try:
        return callback(target)
    except RuntimeError:
        if shiboken6.isValid(target):
            raise
    return default


def _action_kind(action: QAction) -> str:
    group = action.actionGroup()
    if group is not None and group.isExclusive():
        return "select"
    parent = action.parent()
    if isinstance(parent, QMenu) and parent.menuAction() is action:
        return "submenu"
    return "toggle" if action.isCheckable() else "action"


def action_tip(action: QAction) -> str:
    """Describe an action with its authored help, current shortcut and menu semantics."""
    return live_call(action, _action_tip, default="")


def _action_tip(action: QAction) -> str:
    title = plain_label(action.text(), rich=False)
    if not title or action.isSeparator():
        return ""
    text = action.statusTip() or existing_description(title, action)
    if not text:
        text = word(f"ui_tip_{_action_kind(action)}", name=title)
    shortcuts = ", ".join(shortcut.toString(QKeySequence.SequenceFormat.NativeText)
                          for shortcut in action.shortcuts() if not shortcut.isEmpty())
    if shortcuts:
        text += "\n" + word("ui_tip_shortcut", shortcut=shortcuts)
    return text


def _tool_button_tip(widget: QAbstractButton) -> str:
    if not isinstance(widget, QToolButton) or widget.defaultAction() is None:
        return ""
    action = widget.defaultAction()
    authored = action.toolTip()
    if authored and plain_label(authored) != plain_label(action.text()):
        return plain_label(authored)
    return action_tip(action)


def _button_kind(widget: QAbstractButton) -> str:
    if isinstance(widget, QRadioButton):
        return "select"
    return "toggle" if widget.isCheckable() else "action"


def button_tip(widget: QAbstractButton) -> str:
    """Describe a button by its parent's role, its default action or its own label."""
    parent = widget.parentWidget()
    if not widget.text():
        if isinstance(parent, QLineEdit):
            return word("ui_tip_clear_text")
        if isinstance(parent, QTabBar):
            return word("ui_tip_scroll_tabs")
    if description := _tool_button_tip(widget):
        return description
    title = plain_label(widget.text()) or control_label(widget)
    if not title:
        return word("ui_tip_icon_button")
    description = widget.accessibleDescription() or existing_description(title, widget)
    return description or word(f"ui_tip_{_button_kind(widget)}", name=title)
