"""Image Inspector — waveform, RGB parade, false colour and focus peaking.

Pro inspection aids grouped in one tabbed dialog. Each tab renders a pure-NumPy
analysis (see :mod:`Imervue.image.scopes`, :mod:`Imervue.image.false_color`,
:mod:`Imervue.image.focus_peaking`) of the current image. The source is
downscaled first so the views stay responsive at any resolution.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QTabWidget, QVBoxLayout, QWidget

from Imervue.image.ela import error_level_analysis
from Imervue.image.false_color import false_color
from Imervue.image.focus_peaking import focus_peaking
from Imervue.image.scopes import compute_parade, compute_waveform
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_PREVIEW_MAX = 800


def _ndarray_to_qimage(arr: np.ndarray) -> QImage:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        return QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    if arr.shape[2] == 3:
        return QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()


def _load_preview_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX), Image.Resampling.LANCZOS)
    return np.array(img)


class ImageInspectorDialog(QDialog):
    """Tabbed scopes / inspection views for one image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("inspector_title", "Scopes & Inspector"))
        self.setMinimumSize(640, 520)

        rgba = _load_preview_rgba(path)
        self._tabs = QTabWidget()
        self._add_tab(lang.get("inspector_waveform", "Waveform"), compute_waveform(rgba))
        self._add_tab(lang.get("inspector_parade", "RGB Parade"), compute_parade(rgba))
        self._add_tab(lang.get("inspector_false_color", "False Color"), false_color(rgba))
        self._add_tab(lang.get("inspector_focus_peak", "Focus Peaking"), focus_peaking(rgba))
        self._add_tab(lang.get("inspector_ela", "Error Level (ELA)"),
                      error_level_analysis(rgba))

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)

    def _add_tab(self, title: str, arr: np.ndarray) -> None:
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setScaledContents(False)
        label.setPixmap(QPixmap.fromImage(_ndarray_to_qimage(arr)))
        self._tabs.addTab(label, title)


def open_image_inspector(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        ImageInspectorDialog(viewer, str(images[idx])).exec()
