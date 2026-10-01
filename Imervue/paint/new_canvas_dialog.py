"""Paint's File > New Canvas…: pick a size from the presets or type one, and the background.

The presets are :mod:`Imervue.paint.canvas_presets` — paper, manga and screen
sizes that ship with Imervue, then the ones you saved with **Save as Preset…**.
Choosing a preset fills in the width and height; changing either by hand
switches the list back to Custom. OK opens a new tab of that size.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.canvas import DEFAULT_CANVAS_HEIGHT, DEFAULT_CANVAS_WIDTH
from Imervue.paint.canvas_presets import (
    BUILT_IN_PRESETS,
    MAX_DIMENSION_PX,
    MIN_DIMENSION_PX,
    CanvasPreset,
    load_custom_presets,
    save_custom_presets,
)

WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def preset_choices() -> list[CanvasPreset]:
    """The presets the dialog offers: the built-in ones, then your own."""
    return [*BUILT_IN_PRESETS, *load_custom_presets()]


class NewCanvasDialog(QDialog):
    """Size and background for a new Paint canvas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_new_canvas_title", "New Canvas"))
        self._presets: list[CanvasPreset] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        row = QHBoxLayout()
        self._preset_box = QComboBox()
        self._preset_box.currentIndexChanged.connect(self._on_preset)
        row.addWidget(self._preset_box, 1)
        save = QPushButton(lang.get("paint_new_canvas_save_preset", "Save as Preset…"))
        save.clicked.connect(self._ask_preset_name)
        row.addWidget(save)
        form.addRow(lang.get("paint_new_canvas_preset", "Preset:"), row)
        self._width = self._dimension(DEFAULT_CANVAS_WIDTH)
        self._height = self._dimension(DEFAULT_CANVAS_HEIGHT)
        form.addRow(lang.get("paint_new_canvas_width", "Width:"), self._width)
        form.addRow(lang.get("paint_new_canvas_height", "Height:"), self._height)
        self._background = QComboBox()
        self._background.addItem(lang.get("paint_new_canvas_white", "White"), WHITE)
        self._background.addItem(lang.get("paint_new_canvas_transparent", "Transparent"),
                                 TRANSPARENT)
        form.addRow(lang.get("paint_new_canvas_background", "Background:"), self._background)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._fill_presets()

    def _dimension(self, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(MIN_DIMENSION_PX, MAX_DIMENSION_PX)
        spin.setSuffix(" px")
        spin.setValue(value)
        spin.valueChanged.connect(self._on_size_typed)
        return spin

    def _fill_presets(self, select: str = "") -> None:
        lang = language_wrapper.language_word_dict
        self._presets = preset_choices()
        box = self._preset_box
        box.blockSignals(True)
        box.clear()
        box.addItem(lang.get("paint_new_canvas_custom", "Custom"), -1)
        for index, preset in enumerate(self._presets):
            box.addItem(f"{preset.name} — {preset.width_px} × {preset.height_px} px", index)
        box.setCurrentIndex(max(0, next((i + 1 for i, p in enumerate(self._presets)
                                         if p.name == select), 0)))
        box.blockSignals(False)

    def _on_preset(self, row: int) -> None:
        index = self._preset_box.itemData(row)
        if index is None or index < 0:
            return
        preset = self._presets[index]
        for spin, value in ((self._width, preset.width_px), (self._height, preset.height_px)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def _on_size_typed(self, _value: int) -> None:
        self._preset_box.blockSignals(True)
        self._preset_box.setCurrentIndex(0)          # a typed size is a custom one
        self._preset_box.blockSignals(False)

    def _ask_preset_name(self) -> None:  # pragma: no cover - Qt dialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self, lang.get("paint_new_canvas_save_preset", "Save as Preset…"),
            lang.get("paint_new_canvas_preset_name", "Preset name"))
        if ok:
            self.save_preset(name)

    def save_preset(self, name: str) -> bool:
        """Keep the current width and height as your preset *name*; False if refused.

        An empty name or one a preset already has is refused.
        """
        name = str(name).strip()
        if not name or name in {p.name for p in self._presets}:
            return False
        width, height, _fill = self.values()
        save_custom_presets([*load_custom_presets(), CanvasPreset(name, width, height)])
        self._fill_presets(select=name)
        return True

    def values(self) -> tuple[int, int, tuple[int, int, int, int]]:
        """``(width, height, background RGBA)`` as chosen."""
        return self._width.value(), self._height.value(), self._background.currentData()
