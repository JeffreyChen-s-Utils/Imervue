"""Web gallery HTML export dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton,
    QFileDialog, QCheckBox, QLineEdit, QFormLayout, QMessageBox,
)

from Imervue.export.web_gallery import WebGalleryOptions, generate_web_gallery
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.web_gallery_dialog")

_DEFAULT_TITLE = "Web Gallery"


def _title() -> str:
    return language_wrapper.language_word_dict.get("web_gallery_title", _DEFAULT_TITLE)


def open_web_gallery_dialog(ui: ImervueMainWindow) -> None:
    dlg = WebGalleryDialog(ui)
    dlg.exec()


class _GalleryWorkerSignals(QObject):
    done = Signal(str, str)


class _GalleryWorker(QRunnable):
    def __init__(self, images: list[str], out_dir: str, opts: WebGalleryOptions):
        super().__init__()
        self.images = images
        self.out_dir = out_dir
        self.opts = opts
        self.signals = _GalleryWorkerSignals()

    def run(self) -> None:
        try:
            path = generate_web_gallery(self.images, self.out_dir, self.opts)
        except (OSError, ValueError) as exc:
            self.signals.done.emit(self.out_dir, str(exc))
            return
        self.signals.done.emit(str(path), "")


class WebGalleryDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(_title())
        self.setMinimumSize(440, 280)

        layout = QVBoxLayout(self)
        images = self._resolve_images()
        layout.addWidget(QLabel(lang.get(
            "web_gallery_source",
            "{count} image(s) will be included.").format(count=len(images))))

        form = QFormLayout()

        self._title_edit = QLineEdit()
        self._title_edit.setText("Imervue Gallery")
        form.addRow(lang.get("web_gallery_title_label", "Title"), self._title_edit)

        self._thumb_spin = QSpinBox()
        self._thumb_spin.setRange(100, 2000)
        self._thumb_spin.setValue(400)
        self._thumb_spin.setSuffix(" px")
        form.addRow(lang.get("web_gallery_thumb_size", "Thumbnail size"), self._thumb_spin)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(30, 100)
        self._quality_spin.setValue(85)
        form.addRow(lang.get("web_gallery_quality", "Thumbnail quality"), self._quality_spin)

        self._copy_check = QCheckBox(lang.get(
            "web_gallery_copy", "Copy full-size originals (portable)"))
        self._copy_check.setChecked(True)
        form.addRow("", self._copy_check)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._export_btn = QPushButton(lang.get("web_gallery_export", "Export\u2026"))
        self._export_btn.clicked.connect(lambda: self._export(images))
        btn_row.addWidget(self._export_btn)

        close_btn = QPushButton(lang.get("web_gallery_close", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _resolve_images(self) -> list[str]:
        viewer = getattr(self.ui, "viewer", None)
        if viewer is None:
            return []
        selected = getattr(viewer, "selected_tiles", set())
        paths = [p for p in selected if isinstance(p, str)]
        if paths:
            return paths
        return list(getattr(viewer.model, "images", []))

    def _export(self, images: list[str]) -> None:
        lang = language_wrapper.language_word_dict
        if not images:
            QMessageBox.information(
                self,
                _title(),
                lang.get("web_gallery_no_images", "No images to export."),
            )
            return
        out_dir = QFileDialog.getExistingDirectory(
            self,
            lang.get("web_gallery_pick_dir", "Pick output folder"),
        )
        if not out_dir:
            return
        opts = WebGalleryOptions(
            thumb_max_side=self._thumb_spin.value(),
            copy_originals=self._copy_check.isChecked(),
            title=self._title_edit.text().strip() or "Imervue Gallery",
            thumbnail_quality=self._quality_spin.value(),
        )
        self._export_btn.setEnabled(False)
        worker = _GalleryWorker(list(images), out_dir, opts)
        worker.signals.done.connect(self._on_done)
        QThreadPool.globalInstance().start(worker)

    def _on_done(self, path_or_dir: str, error: str) -> None:
        self._export_btn.setEnabled(True)
        lang = language_wrapper.language_word_dict
        if error:
            QMessageBox.warning(
                self,
                _title(),
                lang.get("web_gallery_error", "Export failed: {err}").format(err=error),
            )
            return
        if hasattr(self.ui, "toast"):
            self.ui.toast.info(lang.get(
                "web_gallery_done",
                "Gallery written: {path}").format(path=Path(path_or_dir).name))
        self.close()
