"""Crop / straighten / perspective dialog.

Combines three related geometric edits in one dialog. The crop inputs are
normalised fractions so they round-trip with ``Recipe.crop`` regardless of
the source resolution; straighten writes a new output file because it
rotates by an arbitrary angle (not a quarter turn like ``Recipe.rotate_steps``).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSlider,
    QVBoxLayout,
)

from Imervue.gui._apply_save import load_rgba, output_path
from Imervue.image.dimensions import image_dimensions
from Imervue.gui.dialog_rows import image_save_filter, folder_picker_row, save_path_into
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.image.crop_geometry import (
    ASPECT_PRESETS,
    centered_aspect_crop,
    parse_aspect,
)
from Imervue.image.geometry import CropRect, apply_crop, straighten
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.crop_straighten_dialog")

_ANGLE_SLIDER_STEPS = 150   # ±15° in 0.1° increments


class _Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, angle: float, rect: CropRect | None):
        super().__init__()
        self._src = src
        self._out = out
        self._angle = angle
        self._rect = rect

    def run(self):
        try:
            arr = load_rgba(self._src)
            if abs(self._angle) > 1e-4:
                arr = straighten(arr, self._angle)
            if self._rect is not None:
                arr = apply_crop(arr, self._rect)
            Image.fromarray(arr).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:  # worker must always report
            # A cv2-backed straighten raises ImportError (opencv is optional) or
            # cv2.error, which the narrow except missed → done never fired and the
            # dialog hung with Apply disabled. Always report the failure.
            logger.exception("Crop/straighten failed: %s", exc)
            self.done.emit(False, str(exc))


class CropStraightenDialog(WorkerHostMixin, QDialog):
    def __init__(self, viewer: GPUImageView, path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("crop_title", "Crop / Straighten"))
        self.setMinimumWidth(460)

        self._angle = QSlider(Qt.Orientation.Horizontal)
        self._angle.setRange(-_ANGLE_SLIDER_STEPS, _ANGLE_SLIDER_STEPS)
        self._angle.setValue(0)
        self._angle_label = QLabel("0.0°")
        self._angle.valueChanged.connect(self._update_angle_label)

        self._crop_x = self._make_spin(0.0, 1.0, 0.0)
        self._crop_y = self._make_spin(0.0, 1.0, 0.0)
        self._crop_w = self._make_spin(0.05, 1.0, 1.0)
        self._crop_h = self._make_spin(0.05, 1.0, 1.0)

        self._image_aspect = self._probe_image_aspect()
        self._aspect = QComboBox()
        self._aspect.addItems(ASPECT_PRESETS)
        self._aspect.currentTextChanged.connect(self._apply_aspect_preset)

        form = QFormLayout()
        angle_row = QHBoxLayout()
        angle_row.addWidget(self._angle, 1)
        angle_row.addWidget(self._angle_label)
        form.addRow(lang.get("crop_angle", "Straighten angle:"), angle_row)
        form.addRow(lang.get("crop_aspect", "Aspect ratio:"), self._aspect)
        form.addRow(lang.get("crop_x", "Crop X (0..1):"), self._crop_x)
        form.addRow(lang.get("crop_y", "Crop Y (0..1):"), self._crop_y)
        form.addRow(lang.get("crop_w", "Crop width (0..1):"), self._crop_w)
        form.addRow(lang.get("crop_h", "Crop height (0..1):"), self._crop_h)

        out_row, self._out_edit = folder_picker_row(
            lang.get("crop_output", "Output:"), self._pick_out,
            browse_text=lang.get("export_browse", "Browse..."))
        self._out_edit.setText(self._default_output_path())

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("crop_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    @staticmethod
    def _make_spin(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(minimum, maximum)
        s.setSingleStep(0.05)
        s.setDecimals(3)
        s.setValue(value)
        return s

    def _probe_image_aspect(self) -> float:
        """Upright image width/height for aspect framing; 1.0 if the size can't be read.

        Reads the header only (no pixel decode)."""
        dims = image_dimensions(self._path)
        if dims is None:
            return 1.0
        w, h = dims
        return w / h if h else 1.0

    def _apply_aspect_preset(self, label: str) -> None:
        """Fill the crop fields with the largest centred crop of the chosen
        aspect ratio; 'free' leaves the current crop untouched."""
        ratio = parse_aspect(label)
        if ratio is None:
            return
        fx, fy, fw, fh = centered_aspect_crop(self._image_aspect, ratio)
        self._crop_x.setValue(fx)
        self._crop_y.setValue(fy)
        self._crop_w.setValue(fw)
        self._crop_h.setValue(fh)

    def _update_angle_label(self, v: int) -> None:
        self._angle_label.setText(f"{v / 10.0:.1f}°")

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return output_path(str(p), "crop", p.suffix or ".png")

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        save_path_into(
            self, self._out_edit, lang.get("crop_output", "Output"), image_save_filter())

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        angle = self._angle.value() / 10.0
        rect = CropRect(
            x=self._crop_x.value(), y=self._crop_y.value(),
            w=self._crop_w.value(), h=self._crop_h.value(),
        )
        use_rect = (
            rect.x > 0.001 or rect.y > 0.001
            or rect.w < 0.999 or rect.h < 0.999
        )
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(self._path, out, angle, rect if use_rect else None)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_crop_straighten(viewer: GPUImageView) -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    CropStraightenDialog(viewer, str(path)).exec()
