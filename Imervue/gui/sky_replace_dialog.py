"""Sky replacement / background removal dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.segmentation import remove_background, replace_sky
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.sky_replace_dialog")

_MODES = ("sky_gradient", "bg_transparent", "bg_white")


class _Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, src: str, out: str, mode: str):
        super().__init__()
        self._src = src
        self._out = out
        self._mode = mode

    def run(self):
        try:
            arr = np.asarray(Image.open(self._src).convert("RGBA"))
            if self._mode == "sky_gradient":
                arr = replace_sky(arr)
            elif self._mode == "bg_white":
                arr = remove_background(arr, bg_color=(255, 255, 255, 255))
            else:  # bg_transparent
                arr = remove_background(arr, bg_color=(0, 0, 0, 0))
            Image.fromarray(arr).save(self._out)
            self.done.emit(True, self._out)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.error("Sky/bg replace failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class SkyReplaceDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("sky_title", "Sky / Background"))
        self.setMinimumWidth(420)

        self._mode = QComboBox()
        self._mode.addItem(lang.get("sky_mode_sky", "Replace sky with gradient"),
                           "sky_gradient")
        self._mode.addItem(lang.get("sky_mode_trans",
                                    "Remove background (transparent)"),
                           "bg_transparent")
        self._mode.addItem(lang.get("sky_mode_white",
                                    "Remove background (white)"),
                           "bg_white")

        form = QFormLayout()
        form.addRow(lang.get("sky_mode", "Operation:"), self._mode)

        self._out_edit = QLineEdit(self._default_output_path())
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("sky_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("sky_run", "Apply"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _default_output_path(self) -> str:
        p = Path(self._path)
        return str(p.with_name(f"{p.stem}_sky.png"))

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("sky_output", "Output"), self._out_edit.text(),
            "Images (*.png *.tif)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        mode = self._mode.currentData() or "sky_gradient"
        if mode not in _MODES:
            mode = "sky_gradient"
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(self._path, out, mode)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_sky_replace(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    SkyReplaceDialog(viewer, str(path)).exec()
