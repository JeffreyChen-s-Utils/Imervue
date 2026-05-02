"""Film grain dialog — intensity / size / monochrome / seed."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.film_grain import (
    SIZE_MAX,
    SIZE_MIN,
    FilmGrainOptions,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.film_grain_dialog")

_INTENSITY_STEPS = 100


class FilmGrainDialog(QDialog):
    """Procedural-grain editor writing to ``recipe.extra['film_grain']``."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("film_grain_title", "Film Grain"))
        self.setMinimumWidth(420)

        existing = recipe_store.get_for_path(path) or Recipe()
        opts = FilmGrainOptions.from_dict(existing.extra.get("film_grain"))

        self._enable = QCheckBox(lang.get("film_grain_enable", "Enable film grain"))
        self._enable.setChecked(opts.enabled)
        self._monochrome = QCheckBox(lang.get("film_grain_monochrome", "Monochrome grain"))
        self._monochrome.setChecked(opts.monochrome)

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _INTENSITY_STEPS)
        self._intensity.setValue(int(round(opts.intensity * _INTENSITY_STEPS)))
        self._intensity_label = QLabel(f"{int(opts.intensity * 100)}%")
        self._intensity.valueChanged.connect(
            lambda v: self._intensity_label.setText(f"{v}%"),
        )

        self._size = QSpinBox()
        self._size.setRange(SIZE_MIN, SIZE_MAX)
        self._size.setValue(opts.size)

        self._seed = QSpinBox()
        self._seed.setRange(0, 999999)
        self._seed.setValue(opts.seed)
        self._seed.setSpecialValueText(
            lang.get("film_grain_seed_auto", "Auto"),
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(self._enable)
        form.addRow(self._monochrome)
        form.addRow(
            lang.get("film_grain_intensity", "Intensity:"),
            _slider_with_label(self._intensity, self._intensity_label),
        )
        form.addRow(lang.get("film_grain_size", "Grain size:"), self._size)
        form.addRow(lang.get("film_grain_seed", "Seed:"), self._seed)
        return form

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
        recipe.extra["film_grain"] = FilmGrainOptions(
            enabled=self._enable.isChecked(),
            intensity=self._intensity.value() / _INTENSITY_STEPS,
            size=int(self._size.value()),
            monochrome=self._monochrome.isChecked(),
            seed=int(self._seed.value()),
        ).to_dict()
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def _slider_with_label(slider: QSlider, label: QLabel) -> QWidget:
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(50)
    row.addWidget(label)
    return container


def open_film_grain_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    FilmGrainDialog(viewer, str(images[idx])).exec()
