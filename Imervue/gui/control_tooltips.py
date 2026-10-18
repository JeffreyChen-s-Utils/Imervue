"""Fill missing help across workspaces, late-built dialogs, menus and item views."""
from __future__ import annotations

from html import escape

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSlider, QAbstractSpinBox,
    QApplication, QComboBox, QDialog, QDockWidget, QHeaderView, QKeySequenceEdit,
    QLabel, QLineEdit, QMainWindow, QMenu, QPlainTextEdit, QProgressBar, QRadioButton,
    QScrollBar, QTabBar,
    QTextEdit, QToolButton, QToolTip, QWidget,
)

from Imervue.gui.tooltip_text import (
    control_label, existing_description, plain_label, readable_text, word,
)

_GENERATED = "imervueGeneratedToolTip"
_CANVAS_HELP = {
    "GPUImageView": "ui_tip_browser_canvas",
    "AnnotationCanvas": "ui_tip_modify_canvas",
    "PaintCanvas": "ui_tip_paint_canvas",
    "PuppetCanvas": "ui_tip_puppet_canvas",
    "ColorWheelWidget": "ui_tip_colour_wheel",
    "_CurveCanvas": "tone_curve_canvas_tooltip",
    "PressureCurveEditor": "tone_curve_canvas_tooltip",
    "_StampCanvas": "stamp_hint",
    "_SpotCanvas": "heal_hint",
    "BeforeAfterView": "ui_tip_split_compare",
    "_SplitLabel": "ui_tip_split_compare",
    "_ReferenceView": "ui_tip_pan_zoom",
    "_ImageLabel": "ui_tip_pan_zoom",
    "PoseCanvas": "ui_tip_pose_canvas",
    "_StarLabel": "ui_tip_rating_stars",
    "QSplitterHandle": "ui_tip_resize_panel",
}


def _store(target, text: str) -> None:
    # Qt may replace toolbar/clear buttons as an action's help changes during a walk.
    if text and shiboken6.isValid(target):
        # Plain text format prevents paths/labels containing '<' from becoming rich text.
        formatted = f"<qt>{escape(text).replace(chr(10), '<br>')}</qt>"
        target.setToolTip(formatted)
        target.setProperty(_GENERATED, formatted)


def action_tip(action: QAction) -> str:
    """Describe an action with its authored help, current shortcut and menu semantics."""
    title = plain_label(action.text(), rich=False)
    if not title or action.isSeparator():
        return ""
    text = action.statusTip() or existing_description(title, action)
    if not text:
        parent = action.parent()
        submenu = isinstance(parent, QMenu) and parent.menuAction() is action
        kind = "submenu" if submenu else "toggle" if action.isCheckable() else "action"
        if action.actionGroup() is not None and action.actionGroup().isExclusive():
            kind = "select"
        text = word(f"ui_tip_{kind}", name=title)
    shortcuts = ", ".join(shortcut.toString(QKeySequence.SequenceFormat.NativeText)
                          for shortcut in action.shortcuts() if not shortcut.isEmpty())
    if shortcuts:
        text += "\n" + word("ui_tip_shortcut", shortcut=shortcuts)
    return text


def _button_tip(widget: QAbstractButton) -> str:
    parent = widget.parentWidget()
    if not widget.text():
        if isinstance(parent, QLineEdit):
            return word("ui_tip_clear_text")
        if isinstance(parent, QTabBar):
            return word("ui_tip_scroll_tabs")
    if isinstance(widget, QToolButton) and widget.defaultAction() is not None:
        action = widget.defaultAction()
        authored = action.toolTip()
        if authored and plain_label(authored) != plain_label(action.text()):
            return plain_label(authored)
        if description := action_tip(action):
            return description
    title = plain_label(widget.text()) or control_label(widget)
    if not title:
        return word("ui_tip_icon_button")
    description = widget.accessibleDescription() or existing_description(title, widget)
    kind = ("select" if isinstance(widget, QRadioButton)
            else "toggle" if widget.isCheckable() else "action")
    return description or word(f"ui_tip_{kind}", name=title)


def _field_tip(widget: QWidget) -> str:
    name = control_label(widget) or word("ui_tip_value")
    parent = widget.parentWidget()
    if isinstance(widget, QLineEdit) and isinstance(parent, (QAbstractSpinBox, QComboBox,
                                                           QKeySequenceEdit)):
        return plain_label(parent.toolTip()) if parent.toolTip() else _field_tip(parent)
    description = existing_description(name, widget)
    if isinstance(widget, (QAbstractSpinBox, QAbstractSlider)):
        if hasattr(widget, "minimum") and hasattr(widget, "maximum"):
            suffix = widget.suffix() if hasattr(widget, "suffix") else ""
            limits = word("ui_tip_range", name=name, minimum=f"{widget.minimum()}{suffix}",
                          maximum=f"{widget.maximum()}{suffix}")
            return f"{description}\n{limits}" if description else limits
        return description or word("ui_tip_edit", name=name)
    if isinstance(widget, QKeySequenceEdit):
        return word("ui_tip_key_sequence", name=name)
    if isinstance(widget, QComboBox):
        return description or word(
            "ui_tip_choose_editable" if widget.isEditable() else "ui_tip_choose", name=name)
    return description or word("ui_tip_edit", name=name)


def _widget_tip(widget: QWidget) -> str:
    if help_key := _CANVAS_HELP.get(type(widget).__name__):
        return word(help_key)
    if isinstance(widget, QAbstractButton):
        return _button_tip(widget)
    if isinstance(widget, QAbstractItemView):
        return word("ui_tip_items")
    if isinstance(widget, QScrollBar):
        return word("ui_tip_scroll")
    if isinstance(widget, QProgressBar):
        return word("ui_tip_progress")
    if type(widget).__name__ == "_KeyCaptureEdit":
        return word("ui_tip_key_sequence", name=control_label(widget) or word("ui_tip_value"))
    if isinstance(widget, (QAbstractSpinBox, QAbstractSlider, QComboBox, QLineEdit,
                           QTextEdit, QPlainTextEdit, QKeySequenceEdit)):
        return _field_tip(widget)
    if isinstance(widget, QLabel):
        return readable_text(widget.text())
    if isinstance(widget, QDockWidget):
        if widget.features() & QDockWidget.DockWidgetFeature.DockWidgetMovable:
            return word("ui_tip_dock", name=plain_label(widget.windowTitle()))
        return plain_label(widget.windowTitle())
    return ""


def ensure_tooltip(target) -> None:
    """Keep authored help; refresh generated help when labels, language or ranges change."""
    if not shiboken6.isValid(target):
        return
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
    if not shiboken6.isValid(widget):
        return
    if isinstance(widget, QMenu):
        widget.setToolTipsVisible(True)
        for action in widget.actions():
            ensure_tooltip(action)
    if isinstance(widget, QTabBar):
        previous = widget.property("imervueGeneratedTabTips") or []
        generated = []
        for index in range(widget.count()):
            if not widget.tabToolTip(index) or widget.tabToolTip(index) in previous:
                text = word("ui_tip_tab", name=plain_label(widget.tabText(index)))
                widget.setTabToolTip(index, text)
                generated.append(text)
        widget.setProperty("imervueGeneratedTabTips", generated)


def fill_missing_tooltips(root: QWidget) -> None:
    """Fill constructed controls including hidden tabs without changing existing tooltips."""
    for widget in [root, *root.findChildren(QWidget)]:
        _tabs_and_menu(widget)
        ensure_tooltip(widget)
    for action in root.findChildren(QAction):
        ensure_tooltip(action)


def _item_tip(view: QAbstractItemView, event) -> bool:
    if isinstance(view, QHeaderView):
        section = view.logicalIndexAt(event.pos())
        if section < 0 or view.model() is None:
            return False
        if view.model().headerData(section, view.orientation(), Qt.ItemDataRole.ToolTipRole):
            return False
        value = view.model().headerData(section, view.orientation())
    else:
        index = view.indexAt(event.pos())
        if not index.isValid() or index.data(Qt.ItemDataRole.ToolTipRole):
            return False
        value = index.data(Qt.ItemDataRole.DisplayRole)
    if value is None or str(value) == "":
        return False
    QToolTip.showText(event.globalPos(), f"<qt>{escape(str(value))}</qt>", view.viewport())
    return True


class _ToolTipFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.Type.Show, QEvent.Type.ToolTip):
            return False
        if not isinstance(watched, QWidget):
            return False
        if watched.window().windowType() == Qt.WindowType.ToolTip:
            return False
        if event.type() == QEvent.Type.Show and isinstance(watched, (QMainWindow, QDialog)):
            fill_missing_tooltips(watched)
        if event.type() == QEvent.Type.ToolTip:
            parent = watched.parentWidget()
            if (isinstance(parent, QAbstractItemView) and watched is parent.viewport()
                    and not watched.toolTip() and _item_tip(parent, event)):
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
