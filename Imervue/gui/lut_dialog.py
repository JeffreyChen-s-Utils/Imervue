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
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.lut_dialog")

_SLIDER_STEPS = 100


class LutDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("lut_title", "Apply .cube LUT"))

        recipe = recipe_store.get_for_path(path) or Recipe()
        self._recipe = recipe

        self._path_edit = QLineEdit(recipe.lut_path)
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._browse)
        clear = QPushButton(lang.get("lut_clear", "Clear"))
        clear.clicked.connect(lambda: self._path_edit.setText(""))

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _SLIDER_STEPS)
        self._intensity.setValue(int(round(recipe.lut_intensity * _SLIDER_STEPS)))
        self._intensity_label = QLabel()
        self._intensity.valueChanged.connect(self._update_label)
        self._update_label(self._intensity.value())

        row = QHBoxLayout()
        row.addWidget(QLabel(lang.get("lut_file", ".cube file:")))
        row.addWidget(self._path_edit, 1)
        row.addWidget(browse)
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
            "Pick any Adobe .cube LUT (up to 64³). Intensity blends with the original.",
        )))
        layout.addWidget(buttons)

    def _update_label(self, v: int) -> None:
        self._intensity_label.setText(f"{v}%")

    def _browse(self) -> None:
        lang = language_wrapper.language_word_dict
        start = self._path_edit.text() or str(Path.home())
        fn, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("lut_pick", "Select .cube LUT"),
            start,
            "Cube LUT (*.cube)",
        )
        if fn:
            self._path_edit.setText(fn)

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


def open_lut(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    LutDialog(viewer, str(path)).exec()
