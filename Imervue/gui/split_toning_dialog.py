"""Split toning dialog — writes shadow/highlight tints to recipe.extra."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import get_for_path, set_for_path
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.split_toning_dialog")

_HUE_MAX = 359
_SAT_STEPS = 100
_BAL_STEPS = 100


class SplitToningDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("split_title", "Split Toning"))
        self.setMinimumWidth(440)

        existing = (get_for_path(path) or Recipe()).extra.get("split_toning", {})
        self._shadow_hue = self._slider(0, _HUE_MAX,
                                        int(existing.get("shadow_hue", 210)))
        self._shadow_sat = self._slider(
            0, _SAT_STEPS, int(existing.get("shadow_sat", 0.0) * _SAT_STEPS))
        self._highlight_hue = self._slider(0, _HUE_MAX,
                                           int(existing.get("highlight_hue", 45)))
        self._highlight_sat = self._slider(
            0, _SAT_STEPS,
            int(existing.get("highlight_sat", 0.0) * _SAT_STEPS))
        self._balance = self._slider(
            -_BAL_STEPS, _BAL_STEPS,
            int(existing.get("balance", 0.0) * _BAL_STEPS))

        form = QFormLayout()
        form.addRow(lang.get("split_shadow_hue", "Shadow hue:"),
                    self._row_with_label(self._shadow_hue, self._on_hue_change))
        form.addRow(lang.get("split_shadow_sat", "Shadow saturation:"),
                    self._shadow_sat)
        form.addRow(lang.get("split_highlight_hue", "Highlight hue:"),
                    self._row_with_label(self._highlight_hue, self._on_hue_change))
        form.addRow(lang.get("split_highlight_sat", "Highlight saturation:"),
                    self._highlight_sat)
        form.addRow(lang.get("split_balance", "Balance:"), self._balance)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _slider(minimum: int, maximum: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(minimum, maximum)
        s.setValue(max(minimum, min(maximum, value)))
        return s

    def _row_with_label(self, s: QSlider, _handler) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(s, 1)
        lbl = QLabel(f"{s.value()}°")
        s.valueChanged.connect(lambda v, l=lbl: l.setText(f"{v}°"))
        row.addWidget(lbl)
        return row

    def _on_hue_change(self, _v: int) -> None:
        pass

    def _save(self) -> None:
        existing = get_for_path(self._path) or Recipe()
        existing.extra["split_toning"] = {
            "shadow_hue": float(self._shadow_hue.value()),
            "shadow_sat": self._shadow_sat.value() / _SAT_STEPS,
            "highlight_hue": float(self._highlight_hue.value()),
            "highlight_sat": self._highlight_sat.value() / _SAT_STEPS,
            "balance": self._balance.value() / _BAL_STEPS,
        }
        set_for_path(self._path, existing)
        viewer = self._viewer
        reload_fn = getattr(viewer, "reload_current_image", None)
        if callable(reload_fn):
            reload_fn()
        self.accept()


def open_split_toning(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    SplitToningDialog(viewer, str(path)).exec()
