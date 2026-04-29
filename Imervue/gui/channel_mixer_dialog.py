"""Channel mixer dialog — 3×3 matrix + offsets + monochrome toggle.

Lays out three rows of three weight sliders plus a per-output-channel
offset slider. A monochrome checkbox short-circuits the green and blue
output rows to the red row's weights, which is the canonical recipe
for high-quality black-and-white conversion.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.channel_mixer import (
    OFFSET_MAX,
    OFFSET_MIN,
    WEIGHT_MAX,
    WEIGHT_MIN,
    ChannelMixerOptions,
)
from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.channel_mixer_dialog")


class ChannelMixerDialog(QDialog):
    """3-row weight matrix editor writing to ``recipe.extra['channel_mixer']``."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("channel_mixer_title", "Channel Mixer"))
        self.setMinimumWidth(500)

        existing = recipe_store.get_for_path(path) or Recipe()
        opts = ChannelMixerOptions.from_dict(existing.extra.get("channel_mixer"))

        self._enable = QCheckBox(lang.get("channel_mixer_enable", "Enable channel mixer"))
        self._enable.setChecked(opts.enabled)
        self._monochrome = QCheckBox(lang.get("channel_mixer_monochrome", "Monochrome"))
        self._monochrome.setChecked(opts.monochrome)

        self._red_inputs = self._build_row(opts.red, WEIGHT_MIN, WEIGHT_MAX)
        self._green_inputs = self._build_row(opts.green, WEIGHT_MIN, WEIGHT_MAX)
        self._blue_inputs = self._build_row(opts.blue, WEIGHT_MIN, WEIGHT_MAX)
        self._offset_inputs = self._build_row(opts.offsets, OFFSET_MIN, OFFSET_MAX)

        layout = QVBoxLayout(self)
        layout.addWidget(self._enable)
        layout.addWidget(self._monochrome)
        layout.addLayout(self._build_matrix_grid(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    @staticmethod
    def _build_row(values: list[float], lo: float, hi: float) -> list[QDoubleSpinBox]:
        spins = []
        for v in values:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            spin.setValue(float(v))
            spins.append(spin)
        return spins

    def _build_matrix_grid(self, lang: dict) -> QGridLayout:
        grid = QGridLayout()
        # Header row: empty, R input, G input, B input, Offset
        headers = ["", "R", "G", "B",
                   lang.get("channel_mixer_offset", "Offset")]
        for col, text in enumerate(headers):
            grid.addWidget(QLabel(f"<b>{text}</b>"), 0, col,
                           alignment=Qt.AlignmentFlag.AlignCenter)
        rows = [
            (lang.get("channel_mixer_out_red", "Red →"), self._red_inputs, 0),
            (lang.get("channel_mixer_out_green", "Green →"), self._green_inputs, 1),
            (lang.get("channel_mixer_out_blue", "Blue →"), self._blue_inputs, 2),
        ]
        for row_idx, (label, inputs, offset_idx) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row_idx, 0)
            for col, spin in enumerate(inputs, start=1):
                grid.addWidget(spin, row_idx, col)
            grid.addWidget(self._offset_inputs[offset_idx], row_idx, 4)
        return grid

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
        recipe.extra["channel_mixer"] = ChannelMixerOptions(
            enabled=self._enable.isChecked(),
            monochrome=self._monochrome.isChecked(),
            red=[s.value() for s in self._red_inputs],
            green=[s.value() for s in self._green_inputs],
            blue=[s.value() for s in self._blue_inputs],
            offsets=[s.value() for s in self._offset_inputs],
        ).to_dict()
        recipe_store.set_for_path(self._path, recipe)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def open_channel_mixer_dialog(viewer: GPUImageView) -> None:
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    ChannelMixerDialog(viewer, str(images[idx])).exec()
