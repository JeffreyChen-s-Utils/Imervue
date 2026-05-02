"""Auto colour balance dialog — pick algorithm, preview, save.

Writes the corrected image to ``<name>_balanced.png`` next to the source.
This is a one-shot action rather than a recipe edit because the four
algorithms re-derive their gain factors from the source pixels each
time; storing the output of one run on the recipe (rather than re-running
on demand) avoids the user being surprised when a later edit shifts the
white balance under their feet.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.auto_color_balance import (
    METHODS,
    PERCENTILE_MAX,
    PERCENTILE_MIN,
    RETINEX_RADIUS_MAX,
    RETINEX_RADIUS_MIN,
    AutoBalanceOptions,
    auto_balance,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.auto_color_balance_dialog")

_PERCENT_STEPS = 100


class AutoColorBalanceDialog(QDialog):
    """Pick algorithm + intensity, save corrected output next to source."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("auto_balance_title", "Auto Color Balance"))
        self.setMinimumWidth(440)

        self._method = QComboBox()
        for method in METHODS:
            self._method.addItem(
                lang.get(f"auto_balance_method_{method}", method),
                userData=method,
            )

        self._intensity = QSlider(Qt.Orientation.Horizontal)
        self._intensity.setRange(0, _PERCENT_STEPS)
        self._intensity.setValue(_PERCENT_STEPS)
        self._intensity_label = QLabel("100%")
        self._intensity.valueChanged.connect(
            lambda v: self._intensity_label.setText(f"{v}%"),
        )

        self._percentile = QDoubleSpinBox()
        self._percentile.setRange(PERCENTILE_MIN, PERCENTILE_MAX)
        self._percentile.setSingleStep(0.5)
        self._percentile.setValue(1.0)

        self._retinex_radius = QSpinBox()
        self._retinex_radius.setRange(RETINEX_RADIUS_MIN, RETINEX_RADIUS_MAX)
        self._retinex_radius.setValue(24)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._build_hint(lang))
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("auto_balance_method", "Method:"), self._method)
        form.addRow(
            lang.get("auto_balance_intensity", "Intensity:"),
            _slider_with_label(self._intensity, self._intensity_label),
        )
        form.addRow(
            lang.get("auto_balance_percentile", "Clip percentile:"),
            self._percentile,
        )
        form.addRow(
            lang.get("auto_balance_retinex_radius", "Retinex radius:"),
            self._retinex_radius,
        )
        return form

    @staticmethod
    def _build_hint(lang: dict) -> QLabel:
        msg = lang.get(
            "auto_balance_hint",
            "Writes <name>_balanced.png next to the source. "
            "Percentile applies to 'Auto-levels'; radius applies to 'Retinex'.",
        )
        hint = QLabel(msg)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        return hint

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
        try:
            arr = _load_rgba(self._path)
        except (OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        options = AutoBalanceOptions(
            method=str(self._method.currentData()),
            intensity=self._intensity.value() / _PERCENT_STEPS,
            percentile=float(self._percentile.value()),
            retinex_radius=int(self._retinex_radius.value()),
        )
        try:
            out_arr = auto_balance(arr, options)
        except ValueError as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_balanced.png",
        )
        try:
            Image.fromarray(out_arr, mode="RGBA").save(str(out_path))
        except OSError as exc:
            self._notify_failure(exc)
            return

        self._notify_success(out_path)
        self.accept()

    def _notify_failure(self, exc: Exception) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            prefix = language_wrapper.language_word_dict.get(
                "auto_balance_failed", "Auto balance failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "auto_balance_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def _slider_with_label(slider: QSlider, label: QLabel) -> QWidget:
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, stretch=1)
    label.setMinimumWidth(50)
    row.addWidget(label)
    return container


def open_auto_color_balance_dialog(viewer: GPUImageView) -> None:
    images = list(getattr(viewer.model, "images", []))
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    AutoColorBalanceDialog(viewer, str(images[idx])).exec()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
