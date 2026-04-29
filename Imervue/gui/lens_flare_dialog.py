"""Lens flare dialog — position / intensity / size / colour controls."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.lens_flare import LensFlareOptions
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.lens_flare_dialog")

_PERCENT_STEPS = 100


class LensFlareDialog(QDialog):
    """Configures the flare's position / strength / colour."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("lens_flare_title", "Lens Flare"))
        self.setMinimumWidth(440)

        existing = recipe_store.get_for_path(path) or Recipe()
        opts = LensFlareOptions.from_dict(existing.extra.get("lens_flare"))

        self._enable = QCheckBox(lang.get("lens_flare_enable", "Enable lens flare"))
        self._enable.setChecked(opts.enabled)

        self._x = self._make_pct_slider(int(round(opts.position[0] * _PERCENT_STEPS)))
        self._y = self._make_pct_slider(int(round(opts.position[1] * _PERCENT_STEPS)))
        self._intensity = self._make_pct_slider(
            int(round(opts.intensity * _PERCENT_STEPS)),
        )
        self._size = self._make_pct_slider(int(round(opts.size * _PERCENT_STEPS)))

        self._colour = list(opts.colour)
        self._colour_button = QPushButton()
        self._update_colour_button_swatch()
        self._colour_button.clicked.connect(self._pick_colour)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    @staticmethod
    def _make_pct_slider(value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, _PERCENT_STEPS)
        s.setValue(int(value))
        return s

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(self._enable)
        form.addRow(lang.get("lens_flare_x", "Position X (0–100%):"), self._x)
        form.addRow(lang.get("lens_flare_y", "Position Y (0–100%):"), self._y)
        form.addRow(lang.get("lens_flare_intensity", "Intensity:"), self._intensity)
        form.addRow(lang.get("lens_flare_size", "Halo size:"), self._size)
        form.addRow(lang.get("lens_flare_colour", "Colour:"), self._colour_button)
        return form

    def _update_colour_button_swatch(self) -> None:
        r, g, b = self._colour
        self._colour_button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); min-width: 80px;"
        )
        self._colour_button.setText(f"rgb({r}, {g}, {b})")

    def _pick_colour(self) -> None:
        r, g, b = self._colour
        chosen = QColorDialog.getColor(QColor(r, g, b), self)
        if chosen.isValid():
            self._colour = [chosen.red(), chosen.green(), chosen.blue()]
            self._update_colour_button_swatch()

    def _build_button_box(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        return buttons

    def _commit(self) -> None:
        recipe = recipe_store.get_for_path(self._path) or Recipe()
        recipe.extra["lens_flare"] = LensFlareOptions(
            enabled=self._enable.isChecked(),
            position=[
                self._x.value() / _PERCENT_STEPS,
                self._y.value() / _PERCENT_STEPS,
            ],
            intensity=self._intensity.value() / _PERCENT_STEPS,
            size=max(0.05, self._size.value() / _PERCENT_STEPS),
            colour=list(self._colour),
        ).to_dict()
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def open_lens_flare_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    LensFlareDialog(viewer, str(images[idx])).exec()
