"""
Focus stacking dialog.

Picks a set of images at different focus distances and blends the
sharpest region from each (see :func:`focus_stack_images`).
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

from Imervue.image.focus_stack import FocusStackOptions, stack_focus
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.focus_stack_dialog")


class _StackWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, paths: list[str], out_path: str, opts: FocusStackOptions):
        super().__init__()
        self._paths = paths
        self._out = out_path
        self._opts = opts

    def run(self):
        try:
            rgba = stack_focus(self._paths, self._opts)
            Image.fromarray(rgba).save(self._out)
            self.done.emit(True, self._out)
        except Exception as exc:
            logger.error("Focus stack failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class FocusStackDialog(QDialog):
    def __init__(self, viewer: "GPUImageView"):
        super().__init__(viewer)
        self._viewer = viewer
        self._worker: _StackWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("fstack_title", "Focus Stacking"))
        self.setMinimumWidth(520)

        self._list = QListWidget()
        add_btn = QPushButton(lang.get("fstack_add", "Add images..."))
        clear_btn = QPushButton(lang.get("fstack_clear", "Clear"))
        add_btn.clicked.connect(self._add_files)
        clear_btn.clicked.connect(self._list.clear)

        self._align_check = QCheckBox(lang.get("fstack_align", "Align images"))
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
        self._run_btn.setText(lang.get("fstack_run", "Stack"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("fstack_output", "Output:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(out_browse)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "fstack_hint",
            "Pick a bracket of shots with different focus distances — macro / product shooters.",
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
            self, lang.get("fstack_add", "Add images..."), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp)",
        )
        for f in files:
            self._list.addItem(f)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("fstack_output", "Output"), "stacked.jpg",
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
        opts = FocusStackOptions(align=self._align_check.isChecked())
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _StackWorker(paths, out, opts)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_focus_stack(viewer: "GPUImageView") -> None:
    FocusStackDialog(viewer).exec()
