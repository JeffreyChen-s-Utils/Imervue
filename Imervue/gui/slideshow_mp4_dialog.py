"""Slideshow MP4 export dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QFileDialog, QFormLayout, QMessageBox,
)

from Imervue.export.slideshow_mp4 import SlideshowOptions, generate_slideshow_mp4
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.slideshow_mp4_dialog")


def open_slideshow_mp4_dialog(ui: ImervueMainWindow) -> None:
    dlg = SlideshowMp4Dialog(ui)
    dlg.exec()


class _RenderSignals(QObject):
    done = Signal(str, str)


class _RenderWorker(QRunnable):
    def __init__(self, images: list[str], out: str, opts: SlideshowOptions):
        super().__init__()
        self.images = images
        self.out = out
        self.opts = opts
        self.signals = _RenderSignals()

    def run(self) -> None:
        try:
            generate_slideshow_mp4(self.images, self.out, self.opts)
        except (OSError, ValueError, RuntimeError) as exc:
            self.signals.done.emit(self.out, str(exc))
            return
        self.signals.done.emit(self.out, "")


class SlideshowMp4Dialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("slideshow_mp4_title", "Slideshow Video"))
        self.setMinimumSize(440, 320)

        layout = QVBoxLayout(self)
        images = self._resolve_images()
        layout.addWidget(QLabel(lang.get(
            "slideshow_mp4_source",
            "{count} image(s) will be rendered.").format(count=len(images))))

        form = QFormLayout()

        self._width_spin = QSpinBox()
        self._width_spin.setRange(160, 7680)
        self._width_spin.setValue(1920)
        form.addRow(lang.get("slideshow_width", "Width"), self._width_spin)

        self._height_spin = QSpinBox()
        self._height_spin.setRange(120, 4320)
        self._height_spin.setValue(1080)
        form.addRow(lang.get("slideshow_height", "Height"), self._height_spin)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(10, 60)
        self._fps_spin.setValue(24)
        form.addRow(lang.get("slideshow_fps", "FPS"), self._fps_spin)

        self._hold_spin = QDoubleSpinBox()
        self._hold_spin.setRange(0.2, 30.0)
        self._hold_spin.setValue(3.0)
        self._hold_spin.setSingleStep(0.1)
        self._hold_spin.setSuffix(" s")
        form.addRow(lang.get("slideshow_hold", "Hold per image"), self._hold_spin)

        self._fade_spin = QDoubleSpinBox()
        self._fade_spin.setRange(0.0, 5.0)
        self._fade_spin.setValue(0.5)
        self._fade_spin.setSingleStep(0.1)
        self._fade_spin.setSuffix(" s")
        form.addRow(lang.get("slideshow_fade_seconds", "Fade duration"), self._fade_spin)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 10)
        self._quality_spin.setValue(8)
        form.addRow(lang.get("slideshow_quality", "Quality"), self._quality_spin)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._export_btn = QPushButton(lang.get("slideshow_export", "Export MP4\u2026"))
        self._export_btn.clicked.connect(lambda: self._export(images))
        btn_row.addWidget(self._export_btn)
        close_btn = QPushButton(lang.get("slideshow_close", "Close"))
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
                lang.get("slideshow_mp4_title", "Slideshow Video"),
                lang.get("slideshow_no_images", "No images to export."),
            )
            return
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("slideshow_save_title", "Save Slideshow"),
            "slideshow.mp4",
            "MP4 (*.mp4)",
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".mp4"):
            out_path += ".mp4"
        opts = SlideshowOptions(
            width=self._width_spin.value(),
            height=self._height_spin.value(),
            fps=self._fps_spin.value(),
            hold_seconds=self._hold_spin.value(),
            fade_seconds=self._fade_spin.value(),
            quality=self._quality_spin.value(),
        )
        self._export_btn.setEnabled(False)
        worker = _RenderWorker(list(images), out_path, opts)
        worker.signals.done.connect(self._on_done)
        QThreadPool.globalInstance().start(worker)

    def _on_done(self, out_path: str, error: str) -> None:
        self._export_btn.setEnabled(True)
        lang = language_wrapper.language_word_dict
        if error:
            QMessageBox.warning(
                self,
                lang.get("slideshow_mp4_title", "Slideshow Video"),
                lang.get("slideshow_error", "Export failed: {err}").format(err=error),
            )
            return
        if hasattr(self.ui, "toast"):
            self.ui.toast.info(lang.get(
                "slideshow_done",
                "Slideshow written: {path}").format(path=Path(out_path).name))
        self.close()
