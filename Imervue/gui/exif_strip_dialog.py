"""
EXIF 批次清除
Batch EXIF Strip — remove EXIF / GPS / ICC metadata from all images
in a folder to protect privacy before uploading.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.exif_strip")

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp",
})


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _scan_folder(folder: str) -> list[str]:
    """Return image paths that may contain EXIF data, sorted by name."""
    result: list[str] = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                result.append(entry.path)
    except OSError:
        pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


# ---------------------------------------------------------------------------
# Core strip logic (pure, testable)
# ---------------------------------------------------------------------------

def strip_exif(path: str, *, remove_gps: bool = True, remove_all: bool = True,
               overwrite: bool = True, output_dir: str | None = None) -> str:
    """Strip metadata from an image file.

    Returns the output path on success.
    Raises on failure.
    """
    img = Image.open(path)

    # Preserve ICC profile if user only wants GPS removed
    icc = img.info.get("icc_profile") if not remove_all else None

    # Re-create image from raw bytes — no metadata survives, no list copy
    clean = Image.frombytes(img.mode, img.size, img.tobytes())

    # Determine save path
    if overwrite:
        out_path = path
    else:
        stem = Path(path).stem
        ext = Path(path).suffix
        out_dir = output_dir or str(Path(path).parent)
        out_path = os.path.join(out_dir, f"{stem}_clean{ext}")

    # Save kwargs
    save_kwargs: dict = {}
    fmt = _pil_format(path)
    if fmt:
        save_kwargs["format"] = fmt
    if icc:
        save_kwargs["icc_profile"] = icc

    # For JPEG, preserve quality
    if fmt == "JPEG":
        save_kwargs.setdefault("quality", 95)

    clean.save(out_path, **save_kwargs)
    return out_path


def _pil_format(path: str) -> str | None:
    """Map file extension to Pillow format string."""
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "JPEG", ".jpeg": "JPEG",
        ".png": "PNG", ".tiff": "TIFF", ".tif": "TIFF",
        ".webp": "WebP",
    }.get(ext)


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class _StripWorker(QThread):
    progress = Signal(int, int, str)     # current, total, filename
    result_ready = Signal(int, int)      # success, failed

    def __init__(self, paths: list[str], overwrite: bool,
                 output_dir: str | None, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._overwrite = overwrite
        self._output_dir = output_dir
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        total = len(self._paths)
        success = 0
        failed = 0
        for i, path in enumerate(self._paths):
            if self._abort:
                break
            name = os.path.basename(path)
            self.progress.emit(i + 1, total, name)
            try:
                strip_exif(path, remove_all=True,
                           overwrite=self._overwrite,
                           output_dir=self._output_dir)
                success += 1
            except Exception:
                logger.exception("Failed to strip EXIF from %s", path)
                failed += 1
        self.result_ready.emit(success, failed)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ExifStripDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._lang = language_wrapper.language_word_dict
        self._worker: _StripWorker | None = None

        self.setWindowTitle(
            self._lang.get("exif_strip_title", "Batch EXIF Strip"))
        self.setMinimumSize(550, 300)
        self._build_ui()

        if folder and os.path.isdir(folder):
            self._src_edit.setText(folder)

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        # Source folder
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(lang.get("exif_strip_source", "Source folder:")))
        self._src_edit = QLineEdit()
        src_row.addWidget(self._src_edit, 1)
        browse_btn = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse_folder)
        src_row.addWidget(browse_btn)
        layout.addLayout(src_row)

        # Info
        info = QLabel(lang.get(
            "exif_strip_info",
            "Remove EXIF, GPS, and other metadata from all images in the folder."))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Overwrite checkbox
        self._overwrite_check = QCheckBox(
            lang.get("exif_strip_overwrite", "Overwrite original files"))
        self._overwrite_check.setChecked(True)
        self._overwrite_check.toggled.connect(self._on_overwrite_changed)
        layout.addWidget(self._overwrite_check)

        # Output folder (shown only when not overwriting)
        self._out_row = QHBoxLayout()
        self._out_label = QLabel(lang.get("organizer_output", "Output folder:"))
        self._out_row.addWidget(self._out_label)
        self._out_edit = QLineEdit()
        self._out_row.addWidget(self._out_edit, 1)
        self._out_browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        self._out_browse.clicked.connect(self._browse_out)
        self._out_row.addWidget(self._out_browse)
        layout.addLayout(self._out_row)
        self._out_label.hide()
        self._out_edit.hide()
        self._out_browse.hide()

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(lang.get("organizer_start", "Start"))
        self._start_btn.clicked.connect(self._do_start)
        btn_row.addWidget(self._start_btn)
        btn_row.addStretch()
        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._src_edit.setText(folder)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._out_edit.setText(folder)

    def _on_overwrite_changed(self, checked: bool):
        show = not checked
        self._out_label.setVisible(show)
        self._out_edit.setVisible(show)
        self._out_browse.setVisible(show)

    def _do_start(self):
        src = self._src_edit.text().strip()
        if not src or not os.path.isdir(src):
            return
        paths = _scan_folder(src)
        if not paths:
            self._status_label.setText(
                self._lang.get("exif_strip_no_images",
                               "No supported images found."))
            return

        overwrite = self._overwrite_check.isChecked()
        output_dir = None
        if not overwrite:
            output_dir = self._out_edit.text().strip()
            if not output_dir:
                return
            os.makedirs(output_dir, exist_ok=True)

        self._start_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()

        self._worker = _StripWorker(paths, overwrite, output_dir, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            self._lang.get("exif_strip_processing", "Stripping: {name}")
            .replace("{name}", filename))

    def _on_result(self, success: int, failed: int):
        self._status_label.setText(
            self._lang.get("exif_strip_done",
                           "Done — {success} stripped, {failed} failed.")
            .replace("{success}", str(success))
            .replace("{failed}", str(failed)))

    def _on_finished(self):
        self._progress.hide()
        self._start_btn.setEnabled(True)
        self._worker = None

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            with contextlib.suppress(RuntimeError, TypeError):
                self._worker.disconnect()
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


def open_exif_strip(main_gui: GPUImageView) -> None:
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = ExifStripDialog(main_gui, folder)
    dlg.exec()
