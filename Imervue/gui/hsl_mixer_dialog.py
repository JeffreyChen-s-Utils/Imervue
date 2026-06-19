"""HSL / Colour Mixer dialog — per-band hue/saturation/luminance sliders.

One band is edited at a time (Capture One Colour-Editor style): pick a band,
nudge its three sliders, repeat. The pure math lives in
:mod:`Imervue.image.hsl_mixer`; this is the Qt shell plus a background worker.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QSlider, QVBoxLayout, QWidget

from Imervue.gui._apply_save import (
    apply_save_buttons,
    current_image_path,
    load_rgba,
    notify_saved,
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
            arr = apply_hsl(load_rgba(self._path), self._adjustments)
            Image.fromarray(arr, mode="RGBA").save(self._out)
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

        self._sliders = [self._make_slider(), self._make_slider(), self._make_slider()]

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
        layout.addLayout(apply_save_buttons(self.reject, self._commit))

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
        notify_saved(self._viewer, ok, message, "hsl_failed", "Color mix failed")
        if ok:
            self.accept()


def open_hsl_mixer(viewer: GPUImageView) -> None:
    path = current_image_path(viewer)
    if path:
        HslMixerDialog(viewer, path).exec()
