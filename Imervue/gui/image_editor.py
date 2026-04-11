"""
基本圖片編輯對話框
Image editor — crop, brightness/contrast/saturation, save rotation, format conversion.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageEnhance
from PySide6.QtCore import Qt, QRect, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QFileDialog, QWidget, QSizePolicy, QGroupBox,
    QProgressBar,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


class _CropLabel(QLabel):
    """可拖曳裁剪框的圖片顯示標籤"""

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)
        self._pixmap = None
        self._crop_rect: QRect | None = None
        self._dragging = False
        self._start = None

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._crop_rect = None
        self._update_display()

    def _update_display(self):
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if self._crop_rect:
                painter = QPainter(scaled)
                pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                # 將 crop_rect 從原始座標映射到顯示座標
                sx = scaled.width() / self._pixmap.width()
                sy = scaled.height() / self._pixmap.height()
                r = self._crop_rect
                painter.drawRect(
                    int(r.x() * sx), int(r.y() * sy),
                    int(r.width() * sx), int(r.height() * sy)
                )
                painter.end()
            self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._dragging = True
            self._start = self._to_image_coords(event.position())

    def mouseMoveEvent(self, event):
        if self._dragging and self._pixmap:
            end = self._to_image_coords(event.position())
            if self._start and end:
                x0 = min(self._start[0], end[0])
                y0 = min(self._start[1], end[1])
                x1 = max(self._start[0], end[0])
                y1 = max(self._start[1], end[1])
                self._crop_rect = QRect(x0, y0, x1 - x0, y1 - y0)
                self._update_display()

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _to_image_coords(self, pos):
        if not self._pixmap or not self.pixmap():
            return None
        disp = self.pixmap()
        # 計算圖片在 label 中的偏移
        ox = (self.width() - disp.width()) / 2
        oy = (self.height() - disp.height()) / 2
        sx = self._pixmap.width() / disp.width()
        sy = self._pixmap.height() / disp.height()
        ix = int((pos.x() - ox) * sx)
        iy = int((pos.y() - oy) * sy)
        ix = max(0, min(ix, self._pixmap.width()))
        iy = max(0, min(iy, self._pixmap.height()))
        return ix, iy

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()


class _ImageLoadWorker(QThread):
    """Load a PIL Image off the UI thread."""
    result_ready = Signal(object, str)  # (PIL.Image | None, error_message)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self):
        try:
            if Path(self._path).suffix.lower() == ".svg":
                from Imervue.gpu_image_view.images.image_loader import _load_svg
                img = Image.fromarray(_load_svg(self._path, thumbnail=False))
            else:
                img = Image.open(self._path).convert("RGBA")
            self.result_ready.emit(img, "")
        except Exception as exc:
            self.result_ready.emit(None, str(exc))


class ImageEditorDialog(QDialog):

    def __init__(self, main_gui: GPUImageView, path: str):
        super().__init__(main_gui.main_window)
        self._main_gui = main_gui
        self._path = path
        self._original_img: Image.Image | None = None
        self._edited_img: Image.Image | None = None
        self._loader: _ImageLoadWorker | None = None

        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("editor_title", "Image Editor"))
        self.resize(900, 650)

        main_layout = QHBoxLayout(self)

        # ===== 左側預覽 + 載入指示 =====
        left_col = QVBoxLayout()
        self._preview = _CropLabel()
        left_col.addWidget(self._preview, stretch=1)

        self._loading_label = QLabel(lang.get("editor_loading", "Loading image..."))
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)  # indeterminate
        left_col.addWidget(self._loading_label)
        left_col.addWidget(self._loading_bar)
        main_layout.addLayout(left_col, stretch=3)

        # ===== 右側控制面板 =====
        self._ctrl_container = QWidget()
        ctrl = QVBoxLayout(self._ctrl_container)
        self._ctrl_container.setEnabled(False)

        # 亮度
        bright_grp = QGroupBox(lang.get("editor_brightness", "Brightness"))
        bl = QVBoxLayout(bright_grp)
        self._brightness = QSlider(Qt.Orientation.Horizontal)
        self._brightness.setRange(-100, 100)
        self._brightness.setValue(0)
        self._brightness.valueChanged.connect(self._on_adjust)
        bl.addWidget(self._brightness)
        ctrl.addWidget(bright_grp)

        # 對比
        contrast_grp = QGroupBox(lang.get("editor_contrast", "Contrast"))
        cl = QVBoxLayout(contrast_grp)
        self._contrast = QSlider(Qt.Orientation.Horizontal)
        self._contrast.setRange(-100, 100)
        self._contrast.setValue(0)
        self._contrast.valueChanged.connect(self._on_adjust)
        cl.addWidget(self._contrast)
        ctrl.addWidget(contrast_grp)

        # 飽和度
        sat_grp = QGroupBox(lang.get("editor_saturation", "Saturation"))
        sl = QVBoxLayout(sat_grp)
        self._saturation = QSlider(Qt.Orientation.Horizontal)
        self._saturation.setRange(-100, 100)
        self._saturation.setValue(0)
        self._saturation.valueChanged.connect(self._on_adjust)
        sl.addWidget(self._saturation)
        ctrl.addWidget(sat_grp)

        # 裁剪按鈕
        crop_btn = QPushButton(lang.get("editor_apply_crop", "Apply Crop"))
        crop_btn.clicked.connect(self._apply_crop)
        ctrl.addWidget(crop_btn)

        # 旋轉
        rot_row = QHBoxLayout()
        rot_cw = QPushButton(lang.get("editor_rotate_cw", "Rotate CW"))
        rot_cw.clicked.connect(lambda: self._rotate(90))
        rot_ccw = QPushButton(lang.get("editor_rotate_ccw", "Rotate CCW"))
        rot_ccw.clicked.connect(lambda: self._rotate(-90))
        rot_row.addWidget(rot_ccw)
        rot_row.addWidget(rot_cw)
        ctrl.addLayout(rot_row)

        ctrl.addStretch()

        # 重置
        reset_btn = QPushButton(lang.get("editor_reset", "Reset"))
        reset_btn.clicked.connect(self._reset)
        ctrl.addWidget(reset_btn)

        # 另存
        save_as_btn = QPushButton(lang.get("editor_save_as", "Save As..."))
        save_as_btn.clicked.connect(self._save_as)
        ctrl.addWidget(save_as_btn)

        # 覆蓋儲存
        save_btn = QPushButton(lang.get("editor_save", "Save"))
        save_btn.clicked.connect(self._save)
        ctrl.addWidget(save_btn)

        main_layout.addWidget(self._ctrl_container, stretch=1)

        # ===== 啟動背景載入 =====
        self._loader = _ImageLoadWorker(path)
        self._loader.result_ready.connect(self._on_image_loaded)
        self._loader.finished.connect(self._on_loader_finished)
        self._loader.start()

    def _on_image_loaded(self, img, error: str):
        lang = language_wrapper.language_word_dict
        if img is None:
            self._loading_label.setText(
                lang.get("editor_load_failed", "Failed to load image: {error}").format(error=error)
            )
            self._loading_bar.setRange(0, 1)
            self._loading_bar.setValue(0)
            return

        self._original_img = img
        self._edited_img = img.copy()
        self._loading_label.hide()
        self._loading_bar.hide()
        self._ctrl_container.setEnabled(True)
        self._update_preview()

    def _on_loader_finished(self):
        self._loader = None

    def closeEvent(self, event):
        if self._loader and self._loader.isRunning():
            self._loader.wait(5000)
        super().closeEvent(event)

    def _on_adjust(self):
        if self._edited_img is None:
            return
        img = self._edited_img.copy()

        b_val = self._brightness.value()
        if b_val != 0:
            factor = 1.0 + b_val / 100.0
            img = ImageEnhance.Brightness(img).enhance(factor)

        c_val = self._contrast.value()
        if c_val != 0:
            factor = 1.0 + c_val / 100.0
            img = ImageEnhance.Contrast(img).enhance(factor)

        s_val = self._saturation.value()
        if s_val != 0:
            factor = 1.0 + s_val / 100.0
            img = ImageEnhance.Color(img).enhance(factor)

        self._display_img = img
        self._update_preview(img)

    def _update_preview(self, img=None):
        if img is None:
            img = self._edited_img
        if img is None:
            return
        data = np.array(img)
        h, w = data.shape[:2]
        qimg = QImage(data.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg.copy())
        self._preview.set_image(pixmap)

    def _apply_crop(self):
        rect = self._preview._crop_rect
        if not rect or rect.width() < 2 or rect.height() < 2:
            return
        self._edited_img = self._edited_img.crop((
            rect.x(), rect.y(),
            rect.x() + rect.width(), rect.y() + rect.height()
        ))
        self._preview._crop_rect = None
        self._brightness.setValue(0)
        self._contrast.setValue(0)
        self._saturation.setValue(0)
        self._update_preview()

    def _rotate(self, degrees: int):
        # PIL: positive = CCW, so negate for CW
        self._edited_img = self._edited_img.rotate(-degrees, expand=True)
        self._brightness.setValue(0)
        self._contrast.setValue(0)
        self._saturation.setValue(0)
        self._update_preview()

    def _reset(self):
        self._edited_img = self._original_img.copy()
        self._brightness.setValue(0)
        self._contrast.setValue(0)
        self._saturation.setValue(0)
        self._preview._crop_rect = None
        self._update_preview()

    def _get_final_image(self) -> Image.Image:
        img = self._edited_img.copy()
        b_val = self._brightness.value()
        if b_val != 0:
            img = ImageEnhance.Brightness(img).enhance(1.0 + b_val / 100.0)
        c_val = self._contrast.value()
        if c_val != 0:
            img = ImageEnhance.Contrast(img).enhance(1.0 + c_val / 100.0)
        s_val = self._saturation.value()
        if s_val != 0:
            img = ImageEnhance.Color(img).enhance(1.0 + s_val / 100.0)
        return img

    def _save(self):
        img = self._get_final_image()
        ext = Path(self._path).suffix.lower()
        if ext in (".jpg", ".jpeg"):
            img = img.convert("RGB")
        try:
            img.save(self._path)
            if hasattr(self._main_gui.main_window, "toast"):
                self._main_gui.main_window.toast.success(
                    language_wrapper.language_word_dict.get("editor_saved", "Saved!")
                )
            self.accept()
        except Exception as e:
            if hasattr(self._main_gui.main_window, "toast"):
                self._main_gui.main_window.toast.error(f"Save failed: {e}")

    def _save_as(self):
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("editor_save_as", "Save As..."),
            str(Path(self._path).parent),
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tiff)"
        )
        if not path:
            return
        img = self._get_final_image()
        ext = Path(path).suffix.lower()
        if ext in (".jpg", ".jpeg"):
            img = img.convert("RGB")
        try:
            img.save(path)
            if hasattr(self._main_gui.main_window, "toast"):
                self._main_gui.main_window.toast.success(
                    lang.get("editor_saved", "Saved!")
                )
            self.accept()
        except Exception as e:
            if hasattr(self._main_gui.main_window, "toast"):
                self._main_gui.main_window.toast.error(f"Save failed: {e}")


def open_image_editor(main_gui: GPUImageView):
    images = main_gui.model.images
    if not images or main_gui.current_index >= len(images):
        return
    path = images[main_gui.current_index]
    dlg = ImageEditorDialog(main_gui, path)
    dlg.exec()
