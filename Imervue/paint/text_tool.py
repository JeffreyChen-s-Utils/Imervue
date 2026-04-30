"""Text tool for the Paint workspace.

A click on the canvas opens a small dialog. The user types the text,
picks font / size / colour / bold / italic, and on OK the rendered
glyphs are alpha-composited onto the canvas at the click point.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.text_render import (
    DEFAULT_FAMILY,
    SIZE_MAX,
    SIZE_MIN,
    TextRenderOptions,
    composite_onto,
    render_text,
)

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class TextTool:
    """Dispatcher tool — opens TextDialog on press, composites on accept."""

    def __init__(self, state: ToolState, selection_provider, parent_widget=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._parent = parent_widget

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase != "press":
            return False
        dialog = TextToolDialog(initial_color=self._state.foreground, parent=self._parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        options = dialog.options()
        if not options.text:
            return False
        rendered = render_text(options)
        composite_onto(
            canvas, rendered,
            int(round(evt.x)), int(round(evt.y)),
            selection=self._selection_provider(),
        )
        # Match the foreground state to the colour the user picked so
        # subsequent paint strokes pick up the same shade. Text-tool
        # commit (the dialog OK action) counts as a deliberate pick,
        # so push it into recents.
        self._state.set_foreground(options.color, commit=True)
        return True

    def cancel(self) -> None:
        pass


class TextToolDialog(QDialog):
    """Modal text-entry dialog for the text tool."""

    def __init__(self, initial_color: tuple[int, int, int], parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_text_title", "Add Text"))
        self.setMinimumWidth(420)

        self._color = initial_color
        self._text_edit = QTextEdit()
        self._text_edit.setMinimumHeight(80)
        self._font_box = QFontComboBox()
        self._size = QSpinBox()
        self._size.setRange(SIZE_MIN, SIZE_MAX)
        self._size.setValue(36)
        self._bold = QCheckBox(lang.get("paint_text_bold", "Bold"))
        self._italic = QCheckBox(lang.get("paint_text_italic", "Italic"))
        self._color_btn = QPushButton(lang.get("paint_text_color", "Colour…"))
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_button()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow(lang.get("paint_text_input", "Text:"), self._text_edit)
        form.addRow(lang.get("paint_text_font", "Font:"), self._font_box)
        form.addRow(lang.get("paint_text_size", "Size:"), self._size)
        style_row = QHBoxLayout()
        style_row.addWidget(self._bold)
        style_row.addWidget(self._italic)
        style_row.addWidget(self._color_btn)
        style_row.addStretch(1)
        form.addRow(lang.get("paint_text_style", "Style:"), style_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> TextRenderOptions:
        font = self._font_box.currentFont()
        return TextRenderOptions(
            text=self._text_edit.toPlainText(),
            family=font.family() or DEFAULT_FAMILY,
            size=int(self._size.value()),
            color=self._color,
            bold=self._bold.isChecked(),
            italic=self._italic.isChecked(),
        )

    def _pick_color(self) -> None:  # pragma: no cover - Qt dialog
        col = QColorDialog.getColor(QColor(*self._color), self)
        if col.isValid():
            self._color = (col.red(), col.green(), col.blue())
            self._update_color_button()

    def _update_color_button(self) -> None:
        r, g, b = self._color
        # Darker swatches need white text and vice versa for readability.
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        fg = "#000" if luma > 140 else "#fff"
        self._color_btn.setStyleSheet(
            f"background:rgb({r},{g},{b}); color:{fg}; padding:4px 12px;"
        )
