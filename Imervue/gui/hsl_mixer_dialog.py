"""HSL / Colour Mixer dialog — per-band hue/saturation/luminance sliders.

One band is edited at a time (Capture One Colour-Editor style): pick a band,
nudge its three sliders, repeat. The pure math lives in
:mod:`Imervue.image.hsl_mixer`; this is the Qt shell plus a background worker
that applies all bands and saves a copy.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.hsl_mixer import BANDS, apply_hsl
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.hsl_mixer_dialog")

_SLIDER_RANGE = 100


class _HslWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, path: str, adjustments: dict, out_path: str):
        super().__init__()
        self._path = path
        self._adjustments = adjustments
        self._out = out_path

    def run(self) -> None:
        try:
            arr = _load_rgba(self._path)
            Image.fromarray(apply_hsl(arr, self._adjustments), mode="RGBA").save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("HSL mix failed: %s", exc)
            self.done.emit(False, str(exc))


class HslMixerDialog(QDialog):
    """Per-band HSL adjustment applied to the current image."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _HslWorker | None = None
        self._values: dict[str, list[float]] = {b: [0.0, 0.0, 0.0] for b, _ in BANDS}
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("hsl_title", "HSL / Color Mixer"))
        self.setMinimumWidth(400)

        self._band_combo = QComboBox()
        for band, _centre in BANDS:
            self._band_combo.addItem(lang.get(f"hsl_band_{band}", band.title()), band)
        self._band_combo.currentIndexChanged.connect(self._on_band_changed)

        self._sliders = [
            self._make_slider(),  # hue
            self._make_slider(),  # saturation
            self._make_slider(),  # luminance
        ]

        layout = QVBoxLayout(self)
        layout.addWidget(self._band_combo)
        for key, fallback, slider in zip(
            ("hsl_hue", "hsl_saturation", "hsl_luminance"),
            ("Hue:", "Saturation:", "Luminance:"),
            self._sliders,
            strict=True,
        ):
            layout.addWidget(QLabel(lang.get(key, fallback)))
            layout.addWidget(slider)
        layout.addLayout(self._build_buttons(lang))

    def _make_slider(self) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-_SLIDER_RANGE, _SLIDER_RANGE)
        slider.setValue(0)
        slider.valueChanged.connect(self._on_slider_changed)
        return slider

    def _current_band(self) -> str:
        return self._band_combo.currentData()

    def _on_band_changed(self) -> None:
        stored = self._values[self._current_band()]
        for slider, value in zip(self._sliders, stored, strict=True):
            slider.blockSignals(True)
            slider.setValue(int(value * _SLIDER_RANGE))
            slider.blockSignals(False)

    def _on_slider_changed(self) -> None:
        self._values[self._current_band()] = [
            slider.value() / _SLIDER_RANGE for slider in self._sliders
        ]

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton(lang.get("local_contrast_apply", "Apply & Save"))
        apply_btn.clicked.connect(self._commit)
        row.addWidget(cancel)
        row.addWidget(apply_btn)
        return row

    def _adjustments(self) -> dict[str, tuple[float, float, float]]:
        return {band: tuple(values) for band, values in self._values.items()}

    def _commit(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        out_path = Path(self._path).with_name(f"{Path(self._path).stem}_hsl.png")
        self._worker = _HslWorker(self._path, self._adjustments(), str(out_path))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        lang = language_wrapper.language_word_dict
        toast = getattr(getattr(self._viewer, "main_window", None), "toast", None)
        if toast is not None:
            if ok:
                toast.info(lang.get("local_contrast_done", "Saved {path}").format(
                    path=Path(message).name))
            else:
                toast.error(f"{lang.get('hsl_failed', 'Color mix failed')}: {message}")
        if ok:
            self.accept()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)


def open_hsl_mixer(viewer: GPUImageView) -> None:
    images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
    idx = getattr(viewer, "current_index", -1)
    if 0 <= idx < len(images):
        HslMixerDialog(viewer, str(images[idx])).exec()
