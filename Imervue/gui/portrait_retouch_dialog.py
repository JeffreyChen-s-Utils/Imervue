"""Portrait auto-retouch dialog — skin smoothing + red-eye + eye sharpen."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.portrait_retouch import (
    SMOOTH_RADIUS_MAX,
    SMOOTH_RADIUS_MIN,
    RetouchOptions,
    auto_retouch,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.portrait_retouch_dialog")

_PERCENT_STEPS = 100


class PortraitRetouchDialog(QDialog):
    """Three intensity sliders — skin / red-eye / eye sharpen — plus a radius."""

    def __init__(self, viewer: GPUImageView, path: str, parent=None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("portrait_retouch_title", "Portrait Auto-Retouch"))
        self.setMinimumWidth(440)

        self._smooth = self._make_pct_slider(40)
        self._smooth_radius = QSlider(Qt.Orientation.Horizontal)
        self._smooth_radius.setRange(SMOOTH_RADIUS_MIN, SMOOTH_RADIUS_MAX)
        self._smooth_radius.setValue(4)
        self._red_eye = self._make_pct_slider(60)
        self._sharpen = self._make_pct_slider(30)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        hint = QLabel(
            lang.get(
                "portrait_retouch_hint",
                "Writes <name>_retouched.png next to the source.",
            ),
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)
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
        form.addRow(
            lang.get("portrait_retouch_smooth", "Skin smoothing:"),
            self._smooth,
        )
        form.addRow(
            lang.get("portrait_retouch_smooth_radius", "Smoothing radius:"),
            self._smooth_radius,
        )
        form.addRow(
            lang.get("portrait_retouch_red_eye", "Red-eye removal:"),
            self._red_eye,
        )
        form.addRow(
            lang.get("portrait_retouch_sharpen", "Eye sharpening:"),
            self._sharpen,
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
        try:
            arr = _load_rgba(self._path)
        except (OSError, ValueError) as exc:
            self._notify_failure(exc)
            return

        options = RetouchOptions(
            skin_smooth=self._smooth.value() / _PERCENT_STEPS,
            skin_radius=int(self._smooth_radius.value()),
            red_eye=self._red_eye.value() / _PERCENT_STEPS,
            eye_sharpen=self._sharpen.value() / _PERCENT_STEPS,
        )
        try:
            out_arr = auto_retouch(arr, options)
        except ValueError as exc:
            self._notify_failure(exc)
            return

        out_path = Path(self._path).with_name(
            f"{Path(self._path).stem}_retouched.png",
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
                "portrait_retouch_failed", "Portrait retouch failed",
            )
            self._viewer.main_window.toast.error(f"{prefix}: {exc}")

    def _notify_success(self, out_path: Path) -> None:
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            self._viewer.main_window.toast.info(
                language_wrapper.language_word_dict.get(
                    "portrait_retouch_done", "Saved {path}",
                ).format(path=out_path.name),
            )


def open_portrait_retouch_dialog(viewer: GPUImageView) -> None:
    images = list(getattr(viewer.model, "images", []))
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    PortraitRetouchDialog(viewer, str(images[idx])).exec()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
