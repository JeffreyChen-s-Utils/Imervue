"""Statistical image-stacking dialog.

Collects an aligned burst and reduces it with one of the
:mod:`Imervue.image.stack_blend` modes (mean / median / max / min) —
long-exposure, crowd removal, star trails, light painting.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.stack_blend import (
    STACK_MAX,
    STACK_MEAN,
    STACK_MEDIAN,
    STACK_MIN,
    STACK_SIGMA,
    stack_images,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.stack_blend_dialog")

_MODE_LABELS = (
    (STACK_MEAN, "stack_mean", "Mean (long exposure)"),
    (STACK_MEDIAN, "stack_median", "Median (remove crowds)"),
    (STACK_MAX, "stack_max", "Max / lighten (star trails)"),
    (STACK_MIN, "stack_min", "Min / darken"),
    (STACK_SIGMA, "stack_sigma", "Sigma-clipped mean (reject trails)"),
)


class _StackWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, paths: list[str], out_path: str, mode: str):
        super().__init__()
        self._paths = paths
        self._out = out_path
        self._mode = mode

    def run(self):
        try:
            rgba = stack_images(self._paths, self._mode)
            Image.fromarray(rgba).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError) as exc:
            logger.exception("Image stack failed: %s", exc)
            self.done.emit(False, str(exc))


class StackBlendDialog(QDialog):
    def __init__(self, viewer: GPUImageView, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._worker: _StackWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("stack_blend_title", "Image Stack"))
        self.setMinimumWidth(520)

        self._list = QListWidget()
        add_btn = QPushButton(lang.get("fstack_add", "Add images..."))
        clear_btn = QPushButton(lang.get("fstack_clear", "Clear"))
        add_btn.clicked.connect(self._add_files)
        clear_btn.clicked.connect(self._list.clear)

        self._mode_combo = QComboBox()
        for mode, key, fallback in _MODE_LABELS:
            self._mode_combo.addItem(lang.get(key, fallback), mode)

        self._out_edit = QLineEdit()
        out_browse = QPushButton(lang.get("export_browse", "Browse..."))
        out_browse.clicked.connect(self._pick_out)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("fstack_run", "Stack"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(lang.get("stack_mode_label", "Mode:")))
        mode_row.addWidget(self._mode_combo, 1)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("fstack_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "stack_blend_hint",
            "Pick a burst shot from a fixed position. Frames must already be aligned.",
        )))
        layout.addWidget(self._list, 1)
        layout.addLayout(btn_row)
        layout.addLayout(mode_row)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _add_files(self) -> None:
        lang = language_wrapper.language_word_dict
        files, _ = QFileDialog.getOpenFileNames(
            self, lang.get("fstack_add", "Add images..."), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)",
        )
        for f in files:
            self._list.addItem(f)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("fstack_output", "Output"), "stacked.png",
            "Images (*.png *.jpg *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _collected_paths(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _run(self) -> None:
        paths = self._collected_paths()
        out = self._out_edit.text().strip()
        if len(paths) < 2 or not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        mode = self._mode_combo.currentData() or STACK_MEAN
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _StackWorker(paths, out, mode)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_stack_blend(viewer: GPUImageView) -> None:
    StackBlendDialog(viewer).exec()
