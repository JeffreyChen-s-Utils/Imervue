"""Defringe dialog — desaturate edge fringes, apply and save a copy.

Pure math in :mod:`Imervue.image.defringe`; this is the Qt shell (amount /
edge-threshold sliders + a hue selector, shared background worker).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui._apply_save import (
    EffectWorker,
    apply_save_buttons,
    current_image_path,
    labeled_slider,
    notify_saved,
    output_path,
)
from Imervue.image.defringe import ALL, GREEN, PURPLE, apply_defringe
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_SCALE = 100.0
_AMOUNT_DEFAULT = 100
_THRESHOLD_MIN = 1
_THRESHOLD_DEFAULT = 10
_HUES = (PURPLE, GREEN, ALL)


def _two_dp(value: int) -> str:
    return f"{value / _SCALE:.2f}"


class DefringeDialog(QDialog):
    """Amount / edge-threshold sliders + hue selector that defringe and save a copy."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: EffectWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("defringe_title", "Defringe"))
        self.setMinimumWidth(360)

        self._amount, _, amount_row = labeled_slider(0, 100, _AMOUNT_DEFAULT, _two_dp)
        self._threshold, _, threshold_row = labeled_slider(
            _THRESHOLD_MIN, 100, _THRESHOLD_DEFAULT, _two_dp)
        self._hue = QComboBox()
        self._hue.addItems(_HUES)

        form = QFormLayout()
        form.addRow(lang.get("defringe_amount", "Amount:"), amount_row)
        form.addRow(lang.get("defringe_threshold", "Edge threshold:"), threshold_row)
        form.addRow(lang.get("defringe_hue", "Fringe hue:"), self._hue)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        amount = self._amount.value() / _SCALE
        threshold = self._threshold.value() / _SCALE
        hue = self._hue.currentText()
        self._worker = EffectWorker(
            self._path,
            lambda arr: apply_defringe(arr, amount, threshold, hue),
            output_path(self._path, "defringe"),
        )
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        notify_saved(self._viewer, ok, message, "defringe_failed", "Defringe failed")
        if ok:
            self.accept()


def open_defringe(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        DefringeDialog(viewer, path).exec()
