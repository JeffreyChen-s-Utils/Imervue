"""Deflicker dialog — luminance-normalise a folder of time-lapse frames.

Pure-numpy implementation lives in ``Imervue.image.deflicker``; this
module is the Qt front-end that gathers options, runs a background
worker that loads each frame, applies gain correction, and writes
corrected copies into a ``deflickered/`` subfolder so originals stay
intact.
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
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.deflicker import (
    DeflickerOptions,
    apply_gain,
    compute_gain_factors,
    frame_luminance_means,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.deflicker_dialog")

_SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")


class DeflickerDialog(QDialog):
    """Configure deflicker options, then run the worker."""

    def __init__(
        self, viewer: GPUImageView, image_paths: list[str], parent=None,
    ):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._paths = [p for p in image_paths if p.lower().endswith(_SUPPORTED_EXTS)]
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("deflicker_title", "Deflicker (Time-lapse)"))
        self.setMinimumWidth(440)

        self._mode = QComboBox()
        self._mode.addItem(lang.get("deflicker_mode_rolling", "Rolling mean"),
                           userData="rolling")
        self._mode.addItem(lang.get("deflicker_mode_global", "Global mean"),
                           userData="global_mean")

        self._window = QSpinBox()
        self._window.setRange(1, 99)
        self._window.setValue(9)

        self._progress = QProgressBar()
        self._progress.setRange(0, max(1, len(self._paths)))
        self._progress.setValue(0)

        self._frame_count_label = QLabel(
            lang.get(
                "deflicker_frame_count",
                "{count} frames will be processed.",
            ).format(count=len(self._paths))
        )
        self._frame_count_label.setStyleSheet("color: #888; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        layout.addWidget(self._frame_count_label)
        layout.addWidget(self._progress)
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

        self._worker: DeflickerWorker | None = None

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("deflicker_mode", "Target mode:"), self._mode)
        form.addRow(lang.get("deflicker_window", "Rolling window:"), self._window)
        return form

    def _build_button_box(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._start)
        buttons.rejected.connect(self.reject)
        return buttons

    def _start(self) -> None:
        if not self._paths:
            self.reject()
            return
        opts = DeflickerOptions(
            rolling_window=int(self._window.value()),
            target_mode=str(self._mode.currentData()),
        )
        self._worker = DeflickerWorker(self._paths, opts)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished_with_count.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, written: int) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if hasattr(self._viewer, "main_window") and hasattr(
            self._viewer.main_window, "toast",
        ):
            lang = language_wrapper.language_word_dict
            self._viewer.main_window.toast.info(
                lang.get(
                    "deflicker_done",
                    "Wrote {count} deflickered frames.",
                ).format(count=written),
            )
        self.accept()


class DeflickerWorker(QThread):
    """Background worker that emits progress and writes corrected frames."""

    progress = Signal(int)
    finished_with_count = Signal(int)

    def __init__(self, paths: list[str], options: DeflickerOptions):
        super().__init__()
        self._paths = paths
        self._options = options

    def run(self) -> None:  # pragma: no cover - thread entry
        frames = []
        for idx, path in enumerate(self._paths):
            try:
                frames.append(_load_rgba(path))
            except (OSError, ValueError):
                logger.warning("Skipping unreadable frame: %s", path)
                frames.append(None)
            self.progress.emit(idx + 1)

        valid_frames = [f for f in frames if f is not None]
        if not valid_frames:
            self.finished_with_count.emit(0)
            return
        means = frame_luminance_means(valid_frames)
        gains = compute_gain_factors(means, self._options)

        written = 0
        gain_iter = iter(gains.tolist())
        for path, frame in zip(self._paths, frames, strict=False):
            if frame is None:
                continue
            try:
                gain = next(gain_iter)
            except StopIteration:
                break
            corrected = apply_gain(frame, gain)
            out_dir = Path(path).parent / "deflickered"
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / Path(path).name
            try:
                Image.fromarray(corrected, mode="RGBA").save(str(out_path))
                written += 1
            except OSError:
                logger.warning("Failed to write %s", out_path)
        self.finished_with_count.emit(written)


def open_deflicker_dialog(viewer: GPUImageView) -> None:
    images = list(getattr(viewer.model, "images", []))
    if not images:
        return
    DeflickerDialog(viewer, images).exec()


def _load_rgba(path: str) -> np.ndarray:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img)
