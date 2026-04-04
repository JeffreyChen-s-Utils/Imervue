"""
幻燈片播放
Slideshow mode — auto-advance through images with configurable interval and fade.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QCheckBox, QPushButton, QGraphicsOpacityEffect,
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

        # 淡入淡出效果
        self._opacity_effect = QGraphicsOpacityEffect(main_gui)
        self._opacity_effect.setOpacity(1.0)

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
        # 確保恢復不透明
        self._gui.setGraphicsEffect(None)

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

        gui.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        # 淡出
        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InQuad)

        def on_fade_out_done():
            gui.current_index = next_idx
            gui.load_deep_zoom_image(images[next_idx])

            # 淡入
            self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._fade_in.setDuration(300)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)
            self._fade_in.finished.connect(lambda: gui.setGraphicsEffect(None))
            self._fade_in.start()

        self._fade_out.finished.connect(on_fade_out_done)
        self._fade_out.start()


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
