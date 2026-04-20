"""
Panorama stitching dialog.

Lets the user pick a set of images, choose stitch mode
(panorama vs scans), and runs :func:`stitch_panorama` in a worker.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
)

from Imervue.image.panorama import PanoramaOptions, stitch_panorama
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.panorama_dialog")


class _PanoWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, paths: list[str], out_path: str, opts: PanoramaOptions):
        super().__init__()
        self._paths = paths
        self._out = out_path
        self._opts = opts

    def run(self):
        try:
            rgba = stitch_panorama(self._paths, self._opts)
            Image.fromarray(rgba).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:
            logger.error("Panorama stitch failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class PanoramaDialog(QDialog):
    def __init__(self, viewer: "GPUImageView"):
        super().__init__(viewer)
        self._viewer = viewer
        self._worker: _PanoWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("pano_title", "Panorama Stitch"))
        self.setMinimumWidth(520)

        self._list = QListWidget()
        add_btn = QPushButton(lang.get("pano_add", "Add images..."))
        clear_btn = QPushButton(lang.get("pano_clear", "Clear"))
        add_btn.clicked.connect(self._add_files)
        clear_btn.clicked.connect(self._list.clear)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem(lang.get("pano_mode_panorama", "Panorama"), "panorama")
        self._mode_combo.addItem(lang.get("pano_mode_scans", "Scans (flat documents)"), "scans")
        self._crop_check = QCheckBox(lang.get("pano_crop", "Crop black borders"))
        self._crop_check.setChecked(True)

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
        self._run_btn.setText(lang.get("pano_run", "Stitch"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(lang.get("pano_mode", "Mode:")))
        mode_row.addWidget(self._mode_combo, 1)
        mode_row.addWidget(self._crop_check)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("pano_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "pano_hint",
            "Pick overlapping shots in order. Requires 2+ images with 20–40% overlap.",
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
            self, lang.get("pano_add", "Add images..."), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)",
        )
        for f in files:
            self._list.addItem(f)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("pano_output", "Output"), "panorama.jpg",
            "Images (*.jpg *.png *.tif)",
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
        opts = PanoramaOptions(
            mode=self._mode_combo.currentData(),
            crop_black_borders=self._crop_check.isChecked(),
        )
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _PanoWorker(paths, out, opts)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_panorama(viewer: "GPUImageView") -> None:
    PanoramaDialog(viewer).exec()
