"""OCR result dialog — extract text from the current image and show it.

Runs Tesseract off the UI thread (it can be slow), then displays the
recognised text for copying. Degrades gracefully when OCR is unavailable.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.ocr import OcrUnavailableError, extract_text, ocr_available
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.ocr_dialog")


class OcrDialog(QDialog):
    """Show OCR text for one image with a copy button."""

    def __init__(self, viewer: GPUImageView, path: str, parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._path = path
        self._worker: _OcrWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("ocr_title", "Extract Text (OCR)"))
        self.setMinimumSize(420, 320)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(lang.get("ocr_running", "Running OCR…"))

        layout = QVBoxLayout(self)
        layout.addWidget(self._text)
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        copy = QPushButton(lang.get("ocr_copy", "Copy"))
        copy.clicked.connect(self._copy)
        close = QPushButton(lang.get("common_close", "Close"))
        close.clicked.connect(self.accept)
        row.addWidget(copy)
        row.addWidget(close)
        return row

    def run_ocr(self) -> None:  # pragma: no cover - Qt UI / background thread
        self._worker = _OcrWorker(self._path)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, payload: str) -> None:
        lang = language_wrapper.language_word_dict
        if not ok:
            self._text.setPlainText(payload)
            return
        self._text.setPlainText(payload or lang.get("ocr_empty", "No text found."))

    def _copy(self) -> None:  # pragma: no cover - Qt UI
        QApplication.clipboard().setText(self._text.toPlainText())


class _OcrWorker(QThread):
    """Run OCR off the UI thread; emit the text or an error message."""

    done = Signal(bool, str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self) -> None:  # pragma: no cover - background thread
        try:
            text = extract_text(self._path)
        except (OcrUnavailableError, OSError, ValueError) as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, text)


def open_ocr(main_gui: GPUImageView) -> None:  # pragma: no cover - Qt UI
    """Open the OCR dialog for the current image, or toast if OCR is unavailable."""
    images = getattr(getattr(main_gui, "model", None), "images", None) or []
    idx = getattr(main_gui, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    lang = language_wrapper.language_word_dict
    if not ocr_available():
        main_window = getattr(main_gui, "main_window", None)
        toast = getattr(main_window, "toast", None)
        if toast is not None:
            toast.info(lang.get("ocr_unavailable",
                                "Install Tesseract OCR to extract text."))
        return
    dialog = OcrDialog(main_gui, str(images[idx]))
    dialog.run_ocr()
    dialog.exec()
