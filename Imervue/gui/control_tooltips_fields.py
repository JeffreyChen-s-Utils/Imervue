"""Help text for canvases, value fields, labels, docks and other plain widgets."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSlider, QAbstractSpinBox, QComboBox,
    QDockWidget, QKeySequenceEdit, QLabel, QLineEdit, QPlainTextEdit, QProgressBar,
    QScrollBar, QTextEdit, QWidget,
)

from Imervue.gui.control_tooltips_actions import button_tip
from Imervue.gui.tooltip_text import (
    control_label, existing_description, plain_label, readable_text, word,
)

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


def _numeric_tip(widget: QWidget, name: str, description: str) -> str:
    if not (hasattr(widget, "minimum") and hasattr(widget, "maximum")):
        return description or word("ui_tip_edit", name=name)
    suffix = widget.suffix() if hasattr(widget, "suffix") else ""
    limits = word("ui_tip_range", name=name, minimum=f"{widget.minimum()}{suffix}",
                  maximum=f"{widget.maximum()}{suffix}")
    return f"{description}\n{limits}" if description else limits


def _field_tip(widget: QWidget) -> str:
    name = control_label(widget) or word("ui_tip_value")
    parent = widget.parentWidget()
    if isinstance(widget, QLineEdit) and isinstance(parent, (QAbstractSpinBox, QComboBox,
                                                           QKeySequenceEdit)):
        return plain_label(parent.toolTip()) if parent.toolTip() else _field_tip(parent)
    description = existing_description(name, widget)
    if isinstance(widget, (QAbstractSpinBox, QAbstractSlider)):
        return _numeric_tip(widget, name, description)
    if isinstance(widget, QKeySequenceEdit):
        return word("ui_tip_key_sequence", name=name)
    if isinstance(widget, QComboBox):
        return description or word(
            "ui_tip_choose_editable" if widget.isEditable() else "ui_tip_choose", name=name)
    return description or word("ui_tip_edit", name=name)


def widget_tip(widget: QWidget) -> str:
    """Describe a widget by its class name, control kind or visible label."""
    if help_key := _CANVAS_HELP.get(type(widget).__name__):
        return word(help_key)
    if isinstance(widget, QAbstractButton):
        return button_tip(widget)
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
