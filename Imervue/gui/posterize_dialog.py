"""Threshold / Posterize editor — writes to recipe.extra non-destructively.

A small dialog with two independent sections: a threshold slider for a
binary high-contrast look and a posterize slider for stepped-tonal pop.
Both states round-trip through the recipe so the effect persists across
restarts and applies anywhere the develop pipeline runs (deep zoom,
batch export, contact sheet).
"""
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
    QVBoxLayout,
)

from Imervue.image.posterize import (
    POSTERIZE_MAX_LEVELS,
    POSTERIZE_MIN_LEVELS,
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    PosterizeOptions,
    ThresholdOptions,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.posterize_dialog")


class PosterizeDialog(QDialog):
    """Combined threshold + posterize controller writing to recipe.extra."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        # ``viewer`` is normally a QOpenGLWidget so it can also serve as the
        # parent. Tests inject lightweight stubs and pass parent=None.
        from PySide6.QtWidgets import QWidget
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("posterize_title", "Threshold / Posterize"))
        self.setMinimumWidth(420)

        existing = recipe_store.get_for_path(path) or Recipe()
        threshold = ThresholdOptions.from_dict(existing.extra.get("threshold"))
        posterize = PosterizeOptions.from_dict(existing.extra.get("posterize"))

        self._threshold_check = QCheckBox(
            lang.get("posterize_threshold_enable", "Enable threshold"),
        )
        self._threshold_check.setChecked(threshold.enabled)
        self._threshold_slider = self._make_slider(
            THRESHOLD_MIN, THRESHOLD_MAX, threshold.level,
        )
        self._threshold_label = QLabel(str(threshold.level))
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(str(v)),
        )

        self._posterize_check = QCheckBox(
            lang.get("posterize_levels_enable", "Enable posterize"),
        )
        self._posterize_check.setChecked(posterize.enabled)
        self._posterize_slider = self._make_slider(
            POSTERIZE_MIN_LEVELS, POSTERIZE_MAX_LEVELS, posterize.levels,
        )
        self._posterize_label = QLabel(str(posterize.levels))
        self._posterize_slider.valueChanged.connect(
            lambda v: self._posterize_label.setText(str(v)),
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    @staticmethod
    def _make_slider(low: int, high: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(low, high)
        s.setValue(int(value))
        return s

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(self._threshold_check)
        form.addRow(
            lang.get("posterize_threshold_level", "Threshold level (0–255):"),
            _slider_with_label(self._threshold_slider, self._threshold_label),
        )
        form.addRow(self._posterize_check)
        form.addRow(
            lang.get("posterize_levels_count", "Levels per channel (2–64):"),
            _slider_with_label(self._posterize_slider, self._posterize_label),
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
        recipe = recipe_store.get_for_path(self._path) or Recipe()
        recipe.extra["threshold"] = ThresholdOptions(
            enabled=self._threshold_check.isChecked(),
            level=int(self._threshold_slider.value()),
        ).to_dict()
        recipe.extra["posterize"] = PosterizeOptions(
            enabled=self._posterize_check.isChecked(),
            levels=int(self._posterize_slider.value()),
        ).to_dict()
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def _slider_with_label(slider: QSlider, label: QLabel):
    """Pair a slider with its read-out label in a single horizontal row."""
    from PySide6.QtWidgets import QWidget
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(40)
    row.addWidget(label)
    return container


def open_posterize_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    PosterizeDialog(viewer, str(images[idx])).exec()
