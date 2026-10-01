"""Paint's gradient editor: create, change and delete the saved multi-stop gradients.

The gradient tool paints foreground → background unless the Options bar names a
saved gradient. This dialog edits that list (``gradient_editor.load_gradients``
/ ``save_gradients``): each gradient has a name and two or more colour stops,
the first at 0 % and the last at 100 %. OK saves the whole list; Cancel drops
every change. The stop maths lives in :mod:`Imervue.paint.gradient_editor`.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.gradient_editor import (
    MultiStopGradient,
    add_stop,
    build_lut,
    default_gradient,
    load_gradients,
    move_stop,
    recolour_stop,
    remove_stop,
    save_gradients,
)

_PREVIEW_SIZE = (256, 24)


def unique_name(base: str, taken: set[str]) -> str:
    """*base*, or ``base 2``, ``base 3`` … — the first not in *taken*."""
    name, n = base, 2
    while name in taken:
        name, n = f"{base} {n}", n + 1
    return name


class GradientEditorDialog(QDialog):
    """Saved gradients on the left; the chosen one's name, stops and preview on the right."""

    def __init__(self, parent=None, *, selected: str = "",
                 start: tuple[int, int, int] = (0, 0, 0),
                 end: tuple[int, int, int] = (255, 255, 255)):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("paint_gradient_editor_title", "Gradients"))
        self._gradients: list[MultiStopGradient] = load_gradients()
        self._new_ends = ((*start, 255), (*end, 255))
        self._stop = 0
        layout = QVBoxLayout(self)
        body = QHBoxLayout()
        body.addLayout(self._build_list(lang))
        body.addWidget(self._build_editor(lang), 1)
        layout.addLayout(body)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload_list(next((i for i, g in enumerate(self._gradients) if g.name == selected), 0))

    # ---- building ----------------------------------------------------------

    def _build_list(self, lang: dict) -> QVBoxLayout:
        column = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_gradient_row)
        column.addWidget(self._list)
        row = QHBoxLayout()
        self._new_btn = QPushButton(lang.get("paint_gradient_editor_new", "New"))
        self._new_btn.clicked.connect(self._new_gradient)
        self._delete_btn = QPushButton(lang.get("paint_gradient_editor_delete", "Delete"))
        self._delete_btn.clicked.connect(self._delete_gradient)
        row.addWidget(self._new_btn)
        row.addWidget(self._delete_btn)
        column.addLayout(row)
        return column

    def _build_editor(self, lang: dict) -> QWidget:
        self._editor = QWidget()
        form = QFormLayout(self._editor)
        self._name = QLineEdit()
        self._name.editingFinished.connect(self._rename)
        form.addRow(lang.get("paint_gradient_editor_name", "Name:"), self._name)
        self._preview = QLabel()
        form.addRow(self._preview)
        self._stops = QListWidget()
        self._stops.currentRowChanged.connect(self._on_stop_row)
        form.addRow(lang.get("paint_gradient_editor_stops", "Stops:"), self._stops)
        self._position = QSpinBox()
        self._position.setRange(0, 100)
        self._position.setSuffix(" %")
        self._position.valueChanged.connect(self._on_position)
        form.addRow(lang.get("paint_gradient_editor_position", "Position:"), self._position)
        row = QHBoxLayout()
        self._colour_btn = QPushButton(lang.get("paint_gradient_editor_colour", "Colour…"))
        self._colour_btn.clicked.connect(self._pick_colour)
        self._add_btn = QPushButton(lang.get("paint_gradient_editor_add_stop", "Add stop"))
        self._add_btn.clicked.connect(self._add_stop)
        self._remove_btn = QPushButton(lang.get("paint_gradient_editor_remove_stop", "Remove stop"))
        self._remove_btn.clicked.connect(self._remove_stop)
        for button in (self._colour_btn, self._add_btn, self._remove_btn):
            row.addWidget(button)
        form.addRow(row)
        return self._editor

    # ---- the model ---------------------------------------------------------

    def gradients(self) -> list[MultiStopGradient]:
        """The gradients as edited so far (saved only on OK)."""
        return list(self._gradients)

    def selected_name(self) -> str:
        """Name of the gradient selected in the list, or ``""`` when there is none."""
        row = self._list.currentRow()
        return self._gradients[row].name if 0 <= row < len(self._gradients) else ""

    def _current(self) -> MultiStopGradient | None:
        row = self._list.currentRow()
        return self._gradients[row] if 0 <= row < len(self._gradients) else None

    def _replace(self, gradient: MultiStopGradient) -> None:
        self._gradients[self._list.currentRow()] = gradient
        self._show_gradient()

    # ---- list --------------------------------------------------------------

    def _reload_list(self, row: int) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        self._list.addItems([g.name for g in self._gradients])
        self._list.blockSignals(False)
        self._list.setCurrentRow(min(row, len(self._gradients) - 1))
        self._show_gradient()

    def _on_gradient_row(self, _row: int) -> None:
        self._stop = 0
        self._show_gradient()

    def _new_gradient(self) -> None:
        lang = language_wrapper.language_word_dict
        base = lang.get("paint_gradient_editor_untitled", "Gradient")
        name = unique_name(base, {g.name for g in self._gradients})
        self._gradients.append(default_gradient(name, *self._new_ends))
        self._reload_list(len(self._gradients) - 1)

    def _delete_gradient(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._gradients):
            del self._gradients[row]
            self._reload_list(max(0, row - 1))

    def _rename(self) -> None:
        current = self._current()
        if current is None:
            return
        name = self._name.text().strip()
        others = {g.name for g in self._gradients if g is not current}
        if not name or name in others:
            self._name.setText(current.name)        # empty or taken: keep the old name
            return
        self._gradients[self._list.currentRow()] = MultiStopGradient(name, current.stops)
        self._list.item(self._list.currentRow()).setText(name)

    # ---- stops -------------------------------------------------------------

    def _on_stop_row(self, row: int) -> None:
        if row >= 0:
            self._stop = row
            self._show_stop()

    def _on_position(self, percent: int) -> None:
        current = self._current()
        if current is not None and not self._position.signalsBlocked():
            self._replace(move_stop(current, self._stop, percent / 100))

    def _pick_colour(self) -> None:
        current = self._current()
        if current is None:
            return
        r, g, b, a = current.stops[self._stop].color
        chosen = QColorDialog.getColor(QColor(r, g, b, a), self, "",
                                       QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if chosen.isValid():
            self._replace(recolour_stop(current, self._stop, chosen.getRgb()))

    def _add_stop(self) -> None:
        current = self._current()
        if current is not None:
            gradient, self._stop = add_stop(current)
            self._replace(gradient)

    def _remove_stop(self) -> None:
        current = self._current()
        if current is not None:
            self._replace(remove_stop(current, self._stop))
            self._stop = min(self._stop, len(self._current().stops) - 2)
            self._show_gradient()

    # ---- display -----------------------------------------------------------

    def _show_gradient(self) -> None:
        current = self._current()
        self._editor.setEnabled(current is not None)
        self._delete_btn.setEnabled(current is not None)
        if current is None:
            self._name.clear()
            self._stops.clear()
            self._preview.clear()
            return
        self._name.setText(current.name)
        self._stops.blockSignals(True)
        self._stops.clear()
        self._stops.addItems([f"{round(s.position * 100)} %  #{s.color[0]:02x}{s.color[1]:02x}"
                              f"{s.color[2]:02x}  α {s.color[3]}" for s in current.stops])
        self._stop = max(0, min(self._stop, len(current.stops) - 1))
        self._stops.setCurrentRow(self._stop)
        self._stops.blockSignals(False)
        self._preview.setPixmap(preview_pixmap(current))
        self._show_stop()

    def _show_stop(self) -> None:
        current = self._current()
        inner = 0 < self._stop < len(current.stops) - 1
        self._position.blockSignals(True)
        self._position.setValue(round(current.stops[self._stop].position * 100))
        self._position.blockSignals(False)
        self._position.setEnabled(inner)        # the ends stay at 0 % and 100 %
        self._remove_btn.setEnabled(inner)

    def _save(self) -> None:
        self._rename()
        save_gradients(self._gradients)
        self.accept()


def preview_pixmap(gradient: MultiStopGradient) -> QPixmap:
    """A strip showing *gradient* from left (0 %) to right (100 %)."""
    width, height = _PREVIEW_SIZE
    strip = np.ascontiguousarray(np.repeat(build_lut(gradient, width)[None, :, :], height, axis=0))
    image = QImage(strip.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())
