"""Gradient map dialog — pick from a preset palette + intensity slider.

Editing arbitrary stops via UI is unwieldy for a one-shot effect, so the
dialog ships with classic gradient presets (Sepia, Cyanotype, Fire,
Ocean, Mono). Power users can still hand-edit the recipe JSON if they
want custom stops; the preset list is meant to cover ~90% of use cases.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.gradient_map import GradientMapOptions
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gradient_map_dialog")

_INTENSITY_STEPS = 100

# Each preset is (preset_id, [(position, [r, g, b]), ...]).
GRADIENT_PRESETS: list[tuple[str, list[tuple[float, list[int]]]]] = [
    ("mono", [(0.0, [0, 0, 0]), (1.0, [255, 255, 255])]),
    ("sepia", [(0.0, [60, 30, 10]), (0.5, [180, 130, 70]),
               (1.0, [255, 230, 200])]),
    ("cyanotype", [(0.0, [10, 20, 60]), (0.5, [40, 90, 150]),
                   (1.0, [220, 240, 255])]),
    ("fire", [(0.0, [0, 0, 0]), (0.4, [180, 30, 0]),
              (0.7, [255, 150, 0]), (1.0, [255, 240, 200])]),
    ("ocean", [(0.0, [0, 0, 40]), (0.5, [0, 100, 160]),
               (1.0, [200, 240, 255])]),
    ("magenta_teal", [(0.0, [0, 60, 80]), (0.5, [120, 80, 110]),
                      (1.0, [255, 100, 180])]),
]


class GradientMapDialog(QDialog):
    """Preset-driven gradient-map editor writing to ``recipe.extra``."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("gradient_map_title", "Gradient Map"))
        self.setMinimumWidth(420)

        existing = recipe_store.get_for_path(path) or Recipe()
        opts = GradientMapOptions.from_dict(existing.extra.get("gradient_map"))

        self._enable = QCheckBox(lang.get("gradient_map_enable", "Enable gradient map"))
        self._enable.setChecked(opts.enabled)

        self._preset_combo = QComboBox()
        for preset_id, _ in GRADIENT_PRESETS:
            self._preset_combo.addItem(
                lang.get(f"gradient_map_preset_{preset_id}", preset_id.title()),
                userData=preset_id,
            )
        self._select_matching_preset(opts.stops)

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _INTENSITY_STEPS)
        self._intensity.setValue(int(round(opts.intensity * _INTENSITY_STEPS)))
        self._intensity_label = QLabel(f"{int(opts.intensity * 100)}%")
        self._intensity.valueChanged.connect(
            lambda v: self._intensity_label.setText(f"{v}%"),
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _select_matching_preset(self, stops) -> None:
        """Pick the preset whose stops match ``stops``, else default to mono."""
        target = [(round(p, 3), list(c)) for (p, c) in stops]
        for idx, (_pid, preset_stops) in enumerate(GRADIENT_PRESETS):
            normalised = [(round(p, 3), list(c)) for (p, c) in preset_stops]
            if normalised == target:
                self._preset_combo.setCurrentIndex(idx)
                return
        self._preset_combo.setCurrentIndex(0)

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(self._enable)
        form.addRow(lang.get("gradient_map_preset", "Preset:"), self._preset_combo)
        form.addRow(
            lang.get("gradient_map_intensity", "Intensity:"),
            _slider_with_label(self._intensity, self._intensity_label),
        )
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
        preset_id = self._preset_combo.currentData()
        stops = next(
            (s for (pid, s) in GRADIENT_PRESETS if pid == preset_id),
            GRADIENT_PRESETS[0][1],
        )
        recipe = recipe_store.get_for_path(self._path) or Recipe()
        recipe.extra["gradient_map"] = GradientMapOptions(
            enabled=self._enable.isChecked(),
            intensity=self._intensity.value() / _INTENSITY_STEPS,
            stops=list(stops),
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


def open_gradient_map_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    GradientMapDialog(viewer, str(images[idx])).exec()
