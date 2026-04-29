"""Levels editor — black point / white point / gamma sliders."""
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
    QWidget,
)

from Imervue.image.levels import (
    GAMMA_MAX,
    GAMMA_MIN,
    LEVELS_MAX,
    LEVELS_MIN,
    LevelsOptions,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.levels_dialog")

_GAMMA_STEPS = 100  # slider unit; gamma value = 0.1 + (steps / _GAMMA_STEPS) * range


class LevelsDialog(QDialog):
    """Black / white / gamma editor writing to ``recipe.extra['levels']``."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("levels_title", "Levels"))
        self.setMinimumWidth(420)

        existing = recipe_store.get_for_path(path) or Recipe()
        opts = LevelsOptions.from_dict(existing.extra.get("levels"))

        self._enable = QCheckBox(lang.get("levels_enable", "Enable levels"))
        self._enable.setChecked(opts.enabled)

        self._black = self._make_int_slider(LEVELS_MIN, LEVELS_MAX - 1, opts.black)
        self._white = self._make_int_slider(LEVELS_MIN + 1, LEVELS_MAX, opts.white)
        self._gamma = self._make_int_slider(0, _GAMMA_STEPS,
                                            self._gamma_to_step(opts.gamma))

        self._black_label = QLabel(str(opts.black))
        self._white_label = QLabel(str(opts.white))
        self._gamma_label = QLabel(f"{opts.gamma:.2f}")

        self._black.valueChanged.connect(
            lambda v: self._black_label.setText(str(v)),
        )
        self._white.valueChanged.connect(
            lambda v: self._white_label.setText(str(v)),
        )
        self._gamma.valueChanged.connect(
            lambda step: self._gamma_label.setText(
                f"{self._step_to_gamma(step):.2f}",
            )
        )

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    @staticmethod
    def _make_int_slider(low: int, high: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(low, high)
        s.setValue(int(value))
        return s

    @staticmethod
    def _gamma_to_step(gamma: float) -> int:
        # Map [GAMMA_MIN, GAMMA_MAX] → [0, _GAMMA_STEPS]
        span = GAMMA_MAX - GAMMA_MIN
        clamped = max(GAMMA_MIN, min(GAMMA_MAX, float(gamma)))
        return int(round((clamped - GAMMA_MIN) / span * _GAMMA_STEPS))

    @staticmethod
    def _step_to_gamma(step: int) -> float:
        span = GAMMA_MAX - GAMMA_MIN
        return GAMMA_MIN + (max(0, min(_GAMMA_STEPS, step)) / _GAMMA_STEPS) * span

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(self._enable)
        form.addRow(lang.get("levels_black", "Black point:"),
                    _slider_with_label(self._black, self._black_label))
        form.addRow(lang.get("levels_white", "White point:"),
                    _slider_with_label(self._white, self._white_label))
        form.addRow(lang.get("levels_gamma", "Gamma:"),
                    _slider_with_label(self._gamma, self._gamma_label))
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
        recipe.extra["levels"] = LevelsOptions(
            enabled=self._enable.isChecked(),
            black=int(self._black.value()),
            white=int(self._white.value()),
            gamma=self._step_to_gamma(self._gamma.value()),
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


def open_levels_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    LevelsDialog(viewer, str(images[idx])).exec()
