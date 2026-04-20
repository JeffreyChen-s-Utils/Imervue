"""
Healing Brush / Spot Removal dialog.

Shows the current image; left-click to add a spot, right-click on an
existing spot to remove it. A radius slider controls new-spot size.
On OK, all spots are applied via OpenCV inpainting and the result is
saved to a new output file (healing is not part of the Recipe because
masks can be arbitrarily large).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.healing import HealingSpot, apply_healing
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.healing_brush_dialog")

_HIT_SLACK = 4       # extra pixels around a spot that count as a hit
_PREVIEW_MAX = 720   # longest side for the interactive canvas preview


class _SpotCanvas(QWidget):
    """Click-to-add / right-click-to-remove canvas over a preview image."""

    changed = Signal()

    def __init__(self, pixmap: QPixmap, image_size: tuple[int, int], parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._image_size = image_size  # (w, h) of the source image
        self.setFixedSize(pixmap.size())
        self._spots: list[HealingSpot] = []
        self._radius = 12
        self._method = "telea"

    def set_radius(self, value: int) -> None:
        self._radius = max(1, int(value))

    def set_method(self, method: str) -> None:
        self._method = method if method in ("telea", "ns") else "telea"

    def spots(self) -> list[HealingSpot]:
        return list(self._spots)

    def _scale(self) -> tuple[float, float]:
        iw, ih = self._image_size
        return self.width() / max(1, iw), self.height() / max(1, ih)

    def paintEvent(self, event):  # noqa: N802 - Qt override
        _ = event
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        sx, sy = self._scale()
        pen = QPen(QColor(255, 50, 50), 2)
        painter.setPen(pen)
        for s in self._spots:
            cx, cy = s.x * sx, s.y * sy
            rx, ry = s.radius * sx, s.radius * sy
            painter.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        sx, sy = self._scale()
        x_img = int(event.position().x() / sx)
        y_img = int(event.position().y() / sy)
        if event.button() == Qt.MouseButton.RightButton:
            hit = self._find_hit(x_img, y_img)
            if hit is not None:
                self._spots.pop(hit)
                self.update()
                self.changed.emit()
            return
        self._spots.append(HealingSpot(
            x=x_img, y=y_img, radius=self._radius, method=self._method,
        ))
        self.update()
        self.changed.emit()

    def _find_hit(self, x: int, y: int) -> int | None:
        for i, s in enumerate(self._spots):
            if (x - s.x) ** 2 + (y - s.y) ** 2 <= (s.radius + _HIT_SLACK) ** 2:
                return i
        return None


class _HealWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out_path: str, spots: list[HealingSpot]):
        super().__init__()
        self._src = src
        self._out = out_path
        self._spots = spots

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            result = apply_healing(arr, self._spots)
            Image.fromarray(result).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:
            logger.error("Healing failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class HealingBrushDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _HealWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("heal_title", "Healing Brush"))

        pixmap, img_size = self._build_preview(path)
        self._canvas = _SpotCanvas(pixmap, img_size)

        self._radius_slider = QSlider(Qt.Orientation.Horizontal)
        self._radius_slider.setRange(1, 80)
        self._radius_slider.setValue(self._canvas._radius)
        self._radius_slider.valueChanged.connect(self._canvas.set_radius)

        self._method_combo = QComboBox()
        self._method_combo.addItem(lang.get("heal_telea", "Telea (fast)"), "telea")
        self._method_combo.addItem(lang.get("heal_ns", "Navier-Stokes (smooth)"), "ns")
        self._method_combo.currentIndexChanged.connect(
            lambda _i: self._canvas.set_method(self._method_combo.currentData()),
        )

        self._count_label = QLabel()
        self._canvas.changed.connect(self._update_count)
        self._update_count()

        self._out_edit = QLineEdit(self._default_output_path())
        out_browse = QPushButton(lang.get("export_browse", "Browse..."))
        out_browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("heal_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel(lang.get("heal_radius", "Radius:")))
        opts_row.addWidget(self._radius_slider, 1)
        opts_row.addWidget(QLabel(lang.get("heal_method", "Method:")))
        opts_row.addWidget(self._method_combo)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("heal_run", "Apply & Save"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "heal_hint",
            "Left-click to add a spot; right-click to remove. Radius slider sets new spot size.",
        )))
        layout.addWidget(self._canvas, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(opts_row)
        layout.addWidget(self._count_label)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    @staticmethod
    def _build_preview(path: str) -> tuple[QPixmap, tuple[int, int]]:
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        scale = min(1.0, _PREVIEW_MAX / max(w, h))
        pw, ph = max(1, int(w * scale)), max(1, int(h * scale))
        preview = img.resize((pw, ph), Image.Resampling.LANCZOS)
        arr = np.asarray(preview)
        from PySide6.QtGui import QImage
        qimg = QImage(arr.data, pw, ph, arr.strides[0], QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg.copy()), (w, h)

    def _update_count(self) -> None:
        lang = language_wrapper.language_word_dict
        n = len(self._canvas.spots())
        self._count_label.setText(
            lang.get("heal_count", "{n} spot(s)").format(n=n),
        )

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_healed{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("heal_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        spots = self._canvas.spots()
        if not out or not spots:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _HealWorker(self._path, out, spots)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_healing_brush(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    HealingBrushDialog(viewer, str(path)).exec()
