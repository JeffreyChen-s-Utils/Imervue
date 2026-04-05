"""
幻燈片播放
Slideshow mode — auto-advance through images with configurable interval and fade.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QCheckBox, QPushButton,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class SlideshowController:
    """管理幻燈片播放狀態"""

    def __init__(self, main_gui: GPUImageView, interval_ms: int = 3000, fade: bool = True):
        self._gui = main_gui
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._advance)
        self._fade = fade
        self._running = False
        self._anim = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        gui = self._gui
        if not gui.model.images:
            return

        # 如果目前在 tile grid，進入第一張 DeepZoom
        if gui.tile_grid_mode:
            gui.tile_grid_mode = False
            gui.current_index = 0
            gui.load_deep_zoom_image(gui.model.images[0])

        self._running = True
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._running = False
        if self._anim:
            self._anim.stop()
            self._anim = None
        # 確保恢復不透明
        self._gui._slideshow_opacity = 1.0
        self._gui.update()

    def set_interval(self, ms: int):
        self._timer.setInterval(ms)

    def _advance(self):
        gui = self._gui
        images = gui.model.images
        if not images:
            self.stop()
            return

        next_idx = (gui.current_index + 1) % len(images)

        if self._fade:
            self._fade_transition(next_idx)
        else:
            gui.current_index = next_idx
            gui.load_deep_zoom_image(images[next_idx])

    def _fade_transition(self, next_idx: int):
        gui = self._gui
        images = gui.model.images

        # 淡出
        fade_out = QVariantAnimation()
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InQuad)
        fade_out.valueChanged.connect(self._on_opacity_changed)

        def on_fade_out_done():
            gui.current_index = next_idx
            gui.load_deep_zoom_image(images[next_idx])

            # 淡入
            fade_in = QVariantAnimation()
            fade_in.setDuration(300)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)
            fade_in.valueChanged.connect(self._on_opacity_changed)
            fade_in.finished.connect(lambda: setattr(gui, '_slideshow_opacity', 1.0))
            self._anim = fade_in
            fade_in.start()

        fade_out.finished.connect(on_fade_out_done)
        self._anim = fade_out
        fade_out.start()

    def _on_opacity_changed(self, value):
        self._gui._slideshow_opacity = value
        self._gui.update()


class SlideshowDialog(QDialog):
    """幻燈片設定對話框"""

    def __init__(self, main_gui: GPUImageView):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui

        from Imervue.multi_language.language_wrapper import language_wrapper
        lang = language_wrapper.language_word_dict

        self.setWindowTitle(lang.get("slideshow_title", "Slideshow"))
        self.setFixedSize(320, 180)

        layout = QVBoxLayout(self)

        # 間隔
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel(lang.get("slideshow_interval", "Interval (sec):")))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 60)
        self._interval_spin.setValue(3)
        interval_row.addWidget(self._interval_spin)
        layout.addLayout(interval_row)

        # 淡入淡出
        self._fade_check = QCheckBox(lang.get("slideshow_fade", "Fade transition"))
        self._fade_check.setChecked(True)
        layout.addWidget(self._fade_check)

        # 按鈕
        btn_row = QHBoxLayout()
        start_btn = QPushButton(lang.get("slideshow_start", "Start"))
        start_btn.clicked.connect(self._start)
        btn_row.addWidget(start_btn)

        cancel_btn = QPushButton(lang.get("slideshow_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _start(self):
        gui = self._main_gui
        interval_ms = self._interval_spin.value() * 1000
        fade = self._fade_check.isChecked()

        # 建立或更新 controller
        if not hasattr(gui, '_slideshow') or gui._slideshow is None:
            gui._slideshow = SlideshowController(gui, interval_ms, fade)
        else:
            gui._slideshow.set_interval(interval_ms)
            gui._slideshow._fade = fade

        gui._slideshow.start()
        self.accept()


def open_slideshow_dialog(main_gui: GPUImageView):
    # 如果已在播放，先停止
    if hasattr(main_gui, '_slideshow') and main_gui._slideshow and main_gui._slideshow.running:
        main_gui._slideshow.stop()
        return

    dlg = SlideshowDialog(main_gui)
    dlg.exec()


def stop_slideshow(main_gui: GPUImageView):
    if hasattr(main_gui, '_slideshow') and main_gui._slideshow:
        main_gui._slideshow.stop()
