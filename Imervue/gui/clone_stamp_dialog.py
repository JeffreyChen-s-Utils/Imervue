"""Clone stamp dialog — shift-click source, click destination on a preview."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.clone_stamp import CloneStamp, apply_clone_stamp
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.clone_stamp_dialog")

_PREVIEW_MAX = 720
_SLIDER_STEPS = 100


class _StampCanvas(QWidget):
    """Preview widget — shift+click to set source, click to add a stamp."""

    stamp_added = Signal(object)

    def __init__(self, pixmap: QPixmap, scale: float, parent: QWidget):
        super().__init__(parent)
        self._pixmap = pixmap
        self._scale = scale
        self._source: tuple[int, int] | None = None
        self._stamps: list[CloneStamp] = []
        self._radius = 20
        self.setFixedSize(pixmap.width(), pixmap.height())

    def set_radius(self, value: int) -> None:
        self._radius = max(1, int(value))
        self.update()

    def stamps(self) -> list[CloneStamp]:
        return list(self._stamps)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        px = int(event.position().x() / self._scale)
        py = int(event.position().y() / self._scale)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._source = (px, py)
        elif event.button() == Qt.MouseButton.RightButton and self._stamps:
            self._stamps.pop()
        elif self._source is not None:
            sx, sy = self._source
            stamp = CloneStamp(
                sx=sx, sy=sy, dx=px, dy=py,
                radius=self._radius, feather=0.5,
            )
            self._stamps.append(stamp)
            self.stamp_added.emit(stamp)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)
        if self._source is not None:
            pen = QPen(Qt.GlobalColor.cyan, 2)
            p.setPen(pen)
            sx, sy = self._source
            r = int(self._radius * self._scale)
            p.drawEllipse(int(sx * self._scale) - r, int(sy * self._scale) - r,
                          2 * r, 2 * r)
        pen = QPen(Qt.GlobalColor.red, 2)
        p.setPen(pen)
        for stamp in self._stamps:
            r = int(stamp.radius * self._scale)
            p.drawEllipse(int(stamp.dx * self._scale) - r,
                          int(stamp.dy * self._scale) - r,
                          2 * r, 2 * r)
        p.end()


class _StampWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, stamps: list[CloneStamp]):
        super().__init__()
        self._src = src
        self._out = out
        self._stamps = stamps

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            result = apply_clone_stamp(arr, self._stamps)
            Image.fromarray(result).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Clone stamp failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class CloneStampDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _StampWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("stamp_title", "Clone Stamp"))

        img = Image.open(path).convert("RGBA")
        iw, ih = img.size
        scale = min(1.0, _PREVIEW_MAX / max(iw, ih))
        preview = img.resize((int(iw * scale), int(ih * scale)))
        arr = np.asarray(preview).copy()
        qimg = QImage(arr.data, arr.shape[1], arr.shape[0],
                      arr.shape[1] * 4, QImage.Format.Format_RGBA8888).copy()
        self._canvas = _StampCanvas(QPixmap.fromImage(qimg), scale, self)

        self._radius = QSlider(Qt.Orientation.Horizontal)
        self._radius.setRange(2, 100)
        self._radius.setValue(20)
        self._radius.valueChanged.connect(self._canvas.set_radius)

        form = QFormLayout()
        form.addRow(lang.get("stamp_radius", "Radius (px):"), self._radius)

        hint = QLabel(lang.get(
            "stamp_hint",
            "Shift+click to set source • click to stamp • right-click to undo",
        ))
        hint.setWordWrap(True)

        self._out_edit = QLineEdit(self._default_output_path())
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("stamp_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("stamp_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_clone{p.suffix or '.png'}"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("stamp_output", "Output"), self._out_edit.text(),
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        stamps = self._canvas.stamps()
        if not stamps:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _StampWorker(self._path, out, stamps)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_clone_stamp(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    CloneStampDialog(viewer, str(path)).exec()
