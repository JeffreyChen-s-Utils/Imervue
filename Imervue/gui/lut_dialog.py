"""
.cube LUT picker dialog.

Lets the user browse for a ``.cube`` file (Adobe 3D-LUT format) and
choose an intensity. The path and intensity are persisted on the image's
recipe so the LUT applies non-destructively at render time.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from Imervue.gui.dialog_rows import folder_picker_row, open_path_into
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.lut_dialog")

_SLIDER_STEPS = 100


class LutDialog(QDialog):
    def __init__(self, viewer: GPUImageView, path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("lut_title", "Apply .cube LUT"))

        recipe = recipe_store.get_for_path(path) or Recipe()
        self._recipe = recipe

        row, self._path_edit = folder_picker_row(
            lang.get("lut_file", ".cube file:"), self._browse,
            browse_text=lang.get("export_browse", "Browse..."))
        self._path_edit.setText(recipe.lut_path)
        clear = QPushButton(lang.get("lut_clear", "Clear"))
        clear.clicked.connect(lambda: self._path_edit.setText(""))

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _SLIDER_STEPS)
        self._intensity.setValue(int(round(recipe.lut_intensity * _SLIDER_STEPS)))
        self._intensity_label = QLabel()
        self._intensity.valueChanged.connect(self._update_label)
        self._update_label(self._intensity.value())

        row.addWidget(clear)

        strength = QHBoxLayout()
        strength.addWidget(QLabel(lang.get("lut_intensity", "Intensity:")))
        strength.addWidget(self._intensity, 1)
        strength.addWidget(self._intensity_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addLayout(strength)
        layout.addWidget(QLabel(lang.get(
            "lut_hint",
            "Pick any Adobe .cube LUT (3D up to 65³, 1D up to 65,536 points). "
            "Intensity blends with the original.",
        )))
        layout.addWidget(buttons)

    def _update_label(self, v: int) -> None:
        self._intensity_label.setText(f"{v}%")

    def _browse(self) -> None:
        lang = language_wrapper.language_word_dict
        open_path_into(
            self, self._path_edit, lang.get("lut_pick", "Select .cube LUT"), "Cube LUT (*.cube)",
            start=self._path_edit.text() or str(Path.home()))

    def _commit(self) -> None:
        old = self._recipe
        new = Recipe(**{f.name: getattr(old, f.name) for f in old.__dataclass_fields__.values()})
        new.lut_path = self._path_edit.text().strip()
        new.lut_intensity = self._intensity.value() / _SLIDER_STEPS
        recipe_store.set_for_path(self._path, new)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def open_lut(viewer: GPUImageView) -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    LutDialog(viewer, str(path)).exec()
