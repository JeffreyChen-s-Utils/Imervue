"""
HDR merge dialog.

Multi-file picker → background worker that calls :func:`merge_hdr`
(Mertens exposure fusion — no EXIF shutter-speed data required) →
saves the merged image to a user-chosen output path.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from Imervue.image.hdr_merge import HdrOptions, merge_hdr
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.hdr_merge_dialog")


class _HdrWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, paths: list[str], out_path: str, opts: HdrOptions):
        super().__init__()
        self._paths = paths
        self._out = out_path
        self._opts = opts

    def run(self):
        try:
            rgba = merge_hdr(self._paths, self._opts)
            Image.fromarray(rgba).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:
            logger.error("HDR merge failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class HdrMergeDialog(QDialog):
    def __init__(self, viewer: "GPUImageView"):
        super().__init__(viewer)
        self._viewer = viewer
        self._worker: _HdrWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("hdr_title", "HDR Merge"))
        self.setMinimumWidth(520)

        self._list = QListWidget()
        add_btn = QPushButton(lang.get("hdr_add", "Add images..."))
        clear_btn = QPushButton(lang.get("hdr_clear", "Clear"))
        add_btn.clicked.connect(self._add_files)
        clear_btn.clicked.connect(self._list.clear)

        self._align_check = QCheckBox(lang.get("hdr_align", "Align exposures"))
        self._align_check.setChecked(True)

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
        self._run_btn.setText(lang.get("hdr_run", "Merge"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("hdr_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "hdr_hint",
            "Pick 2+ differently-exposed shots (Mertens exposure fusion).",
        )))
        layout.addWidget(self._list, 1)
        layout.addLayout(btn_row)
        layout.addWidget(self._align_check)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _add_files(self) -> None:
        lang = language_wrapper.language_word_dict
        files, _ = QFileDialog.getOpenFileNames(
            self, lang.get("hdr_add", "Add images..."), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)",
        )
        for f in files:
            self._list.addItem(f)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("hdr_output", "Output"), "merged.png",
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
        opts = HdrOptions(method="mertens", align=self._align_check.isChecked())
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _HdrWorker(paths, out, opts)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_hdr_merge(viewer: "GPUImageView") -> None:
    HdrMergeDialog(viewer).exec()
