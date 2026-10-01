"""Slideshow MP4 export dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QFileDialog, QFormLayout, QMessageBox,
)

from Imervue.export.slideshow_effects import TRANSITIONS
from Imervue.export.slideshow_mp4 import SlideshowOptions, generate_slideshow_mp4
from Imervue.gpu_image_view.actions.select import selection_or_all
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.slideshow_mp4_dialog")

_DEFAULT_TITLE = "Slideshow Video"


def _title() -> str:
    return language_wrapper.language_word_dict.get("slideshow_mp4_title", _DEFAULT_TITLE)


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


# Transition key (slideshow_effects.TRANSITIONS) -> label translation key and fallback.
_TRANSITION_LABELS = {
    "fade": ("slideshow_transition_fade", "Fade"),
    "dissolve": ("slideshow_transition_dissolve", "Dissolve"),
    "slide_left": ("slideshow_transition_slide_left", "Slide left"),
    "slide_right": ("slideshow_transition_slide_right", "Slide right"),
    "slide_up": ("slideshow_transition_slide_up", "Slide up"),
    "slide_down": ("slideshow_transition_slide_down", "Slide down"),
    "wipe_left": ("slideshow_transition_wipe_left", "Wipe left"),
    "wipe_right": ("slideshow_transition_wipe_right", "Wipe right"),
}

# attribute, spin class, (min, max), default, step (None = keep), suffix,
# label key / fallback, tooltip key / fallback — one row of the settings form each.
_SETTINGS_ROWS = (
    ("_width_spin", QSpinBox, (160, 7680), 1920, None, "",
     ("slideshow_width", "Width"),
     ("slideshow_width_tooltip", "Output video width in pixels (default 1920 = HD)")),
    ("_height_spin", QSpinBox, (120, 4320), 1080, None, "",
     ("slideshow_height", "Height"),
     ("slideshow_height_tooltip", "Output video height in pixels (default 1080 = HD)")),
    ("_fps_spin", QSpinBox, (10, 60), 24, None, "",
     ("slideshow_fps", "FPS"),
     ("slideshow_fps_tooltip",
      "Frames per second — 24 is cinematic, 30 / 60 are common for screen playback")),
    ("_hold_spin", QDoubleSpinBox, (0.2, 30.0), 3.0, 0.1, " s",
     ("slideshow_hold", "Hold per image"),
     ("slideshow_hold_tooltip", "Seconds each image stays on-screen before the fade")),
    ("_fade_spin", QDoubleSpinBox, (0.0, 5.0), 0.5, 0.1, " s",
     ("slideshow_fade_seconds", "Transition duration"),
     ("slideshow_fade_seconds_tooltip",
      "Length of the transition between consecutive images. Set to 0 for hard cuts.")),
    ("_quality_spin", QSpinBox, (1, 10), 8, None, "",
     ("slideshow_quality", "Quality"),
     ("slideshow_quality_tooltip", "Encoder quality (1 worst / smallest, 10 best / largest)")),
)


class SlideshowMp4Dialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(_title())
        self.setMinimumSize(440, 320)

        layout = QVBoxLayout(self)
        images = self._resolve_images()
        layout.addWidget(QLabel(lang.get(
            "slideshow_mp4_source",
            "{count} image(s) will be rendered.").format(count=len(images))))
        layout.addLayout(self._build_settings_form(lang))
        layout.addLayout(self._build_button_row(lang, images))

    def _build_settings_form(self, lang: dict) -> QFormLayout:
        """Size, frame rate, timing and quality spins, stored as ``self.<attribute>``."""
        form = QFormLayout()
        for attr, cls, (lo, hi), default, step, suffix, label, tooltip in _SETTINGS_ROWS:
            spin = cls()
            spin.setRange(lo, hi)
            spin.setValue(default)
            if step is not None:
                spin.setSingleStep(step)
            if suffix:
                spin.setSuffix(suffix)
            spin.setToolTip(lang.get(*tooltip))
            setattr(self, attr, spin)
            form.addRow(lang.get(*label), spin)
        self._transition_combo = QComboBox()
        for key in TRANSITIONS:
            self._transition_combo.addItem(lang.get(*_TRANSITION_LABELS[key]), key)
        form.addRow(lang.get("slideshow_transition", "Transition"), self._transition_combo)
        return form

    def _build_button_row(self, lang: dict, images: list[str]) -> QHBoxLayout:
        """Right-aligned Export (for *images*) and Close."""
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._export_btn = QPushButton(lang.get("slideshow_export", "Export MP4…"))
        self._export_btn.clicked.connect(lambda: self._export(images))
        btn_row.addWidget(self._export_btn)
        close_btn = QPushButton(lang.get("slideshow_close", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        return btn_row

    def _resolve_images(self) -> list[str]:
        return selection_or_all(getattr(self.ui, "viewer", None))

    def _export(self, images: list[str]) -> None:
        lang = language_wrapper.language_word_dict
        if not images:
            QMessageBox.information(
                self,
                _title(),
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
            transition=self._transition_combo.currentData(),
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
                _title(),
                lang.get("slideshow_error", "Export failed: {err}").format(err=error),
            )
            return
        if hasattr(self.ui, "toast"):
            self.ui.toast.info(lang.get(
                "slideshow_done",
                "Slideshow written: {path}").format(path=Path(out_path).name))
        self.close()
