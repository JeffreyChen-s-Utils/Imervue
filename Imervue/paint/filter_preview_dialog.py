"""Generic single-slider filter preview dialog.

Most filters in :mod:`Imervue.paint.filter_menu` take one
parameter — blur radius, sharpen amount, halftone dot size — and
the user wants live preview as they drag the slider. Wiring a
bespoke dialog for each one duplicates a lot of plumbing; this
module provides one reusable surface that takes a callable plus
the slider config and runs the filter on a debounced timer.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

DEBOUNCE_INTERVAL_MS = 80
PREVIEW_MAX_DIMENSION = 480

# Filter callable signature: ``filter_fn(image, value) -> result``
# where both arrays are HxWx4 uint8 RGBA. The dialog never mutates
# the input; the result is the new buffer the user accepts.
FilterFn = Callable[[np.ndarray, float], np.ndarray]


class FilterPreviewDialog(QDialog):
    """Dialog wrapping a single-parameter filter with live preview.

    Construction args:

    * ``image`` — the source HxWx4 uint8 RGBA buffer.
    * ``filter_fn`` — callable invoked as ``filter_fn(image, value)``;
      the value comes from the slider, scaled per ``value_scale``.
    * ``slider_min`` / ``slider_max`` / ``slider_default`` — slider
      bounds in slider-space integers. The actual filter sees
      ``slider_value × value_scale``.
    * ``label_format`` — Python format string applied to the
      slider's *scaled* value to label it (e.g. ``"{:.1f}"``).
    """

    def __init__(
        self,
        image: np.ndarray,
        filter_fn: FilterFn,
        *,
        slider_min: int = 0,
        slider_max: int = 100,
        slider_default: int = 50,
        value_scale: float = 1.0,
        label_format: str = "{:g}",
        title_key: str = "paint_filter_preview_title",
        parent=None,
    ):
        super().__init__(parent)
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError(
                f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
            )
        if slider_min >= slider_max:
            raise ValueError(
                f"slider_min must be < slider_max, got "
                f"{slider_min} / {slider_max}",
            )
        if not slider_min <= slider_default <= slider_max:
            raise ValueError(
                f"slider_default {slider_default} outside "
                f"[{slider_min}, {slider_max}]",
            )

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get(title_key, "Filter"))

        self._source = image
        self._filter_fn = filter_fn
        self._value_scale = float(value_scale)
        self._label_format = str(label_format)
        self._working = image.copy()

        layout = QVBoxLayout(self)

        self._preview = QLabel()
        self._preview.setMinimumSize(320, 240)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background:#222;")
        layout.addWidget(self._preview, stretch=1)

        slider_row = QHBoxLayout()
        slider_label = QLabel(lang.get(
            "paint_filter_preview_value", "Value:",
        ))
        slider_row.addWidget(slider_label)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(slider_min), int(slider_max))
        self._slider.setValue(int(slider_default))
        self._slider.valueChanged.connect(self._on_slider_changed)
        slider_row.addWidget(self._slider, stretch=1)
        self._value_label = QLabel(self._format_value(slider_default))
        slider_row.addWidget(self._value_label)
        layout.addLayout(slider_row)

        # Debounce: re-running the filter on every slider tick is too
        # slow for non-trivial filters; coalesce into one update per
        # ``DEBOUNCE_INTERVAL_MS`` while the user keeps dragging.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_INTERVAL_MS)
        self._debounce.timeout.connect(self._refresh_preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Render the initial preview immediately (no debounce).
        self._refresh_preview()

    # ---- public API ------------------------------------------------------

    def working_image(self) -> np.ndarray:
        """The most recent filter result (caller commits on Ok)."""
        return self._working

    def slider_value(self) -> float:
        """Current slider value in scaled (filter-input) units."""
        return self._slider.value() * self._value_scale

    # ---- internals -------------------------------------------------------

    def _on_slider_changed(self, raw_value: int) -> None:
        self._value_label.setText(self._format_value(raw_value))
        # Restart the debounce timer rather than fire immediately —
        # a fast drag will accumulate ticks into one filter pass.
        self._debounce.start()

    def _refresh_preview(self) -> None:
        scaled = float(self._slider.value()) * self._value_scale
        try:
            self._working = self._filter_fn(self._source, scaled)
        except (ValueError, RuntimeError):
            # Filter rejected the value — keep the previous working
            # image so the preview doesn't go blank mid-drag.
            return
        self._update_preview_pixmap()

    def _update_preview_pixmap(self) -> None:  # pragma: no cover - Qt UI
        h, w = self._working.shape[:2]
        qimage = QImage(
            bytes(self._working.tobytes()),
            w, h, w * 4, QImage.Format.Format_RGBA8888,
        )
        cap = PREVIEW_MAX_DIMENSION
        if max(h, w) > cap:
            qimage = qimage.scaled(
                cap, cap,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._preview.setPixmap(QPixmap.fromImage(qimage))

    def _format_value(self, raw_slider_value: int) -> str:
        return self._label_format.format(
            float(raw_slider_value) * self._value_scale,
        )
