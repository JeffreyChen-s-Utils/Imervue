"""Manual censor editor for the safety_review plugin.

When the detector misses a region, censors the wrong place, or the box is the
wrong size, this dialog gives the user direct control: draw censor boxes over
the image by hand, move / delete them, then apply. The censoring is applied to
exactly the boxes the user drew — no detection — so the result is fully
predictable.

The interaction geometry lives in :mod:`_manual` (pure, unit-tested); the
canvas here is a thin Qt shell over it. ``ManualReviewDialog`` is a plain
``QDialog`` / ``QWidget`` (no ``QOpenGLWidget``), so it needs no headless-CI
skip marker.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

from safety_review._constants import (
    DEFAULT_BLOCK_SIZE,
    SHAPE_ELLIPSE,
    SHAPE_RECT,
    STYLE_BLACK,
    STYLE_BLUR,
    STYLE_MOSAIC,
)
from safety_review._detection import _process_manual_image
from safety_review._manual import (
    clamp_region,
    fit_scale,
    is_valid_region,
    move_region,
    normalize_rect,
    region_at,
    to_display_rect,
    to_image_point,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

_MAX_CANVAS_W = 1100
_MAX_CANVAS_H = 720


def _load_pixmap(path: str) -> QPixmap:
    """Load *path* as a QPixmap, falling back to Pillow for formats Qt can't
    decode natively (so RAW/HEIF etc. still open for manual review)."""
    pixmap = QPixmap(path)
    if not pixmap.isNull():
        return pixmap
    try:
        from PIL import Image
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
            qim = QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height,
                         QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qim.copy())
    except Exception:
        logger.error("Manual review couldn't load %s", path, exc_info=True)
        return QPixmap()


class _ManualCanvas(QWidget):
    """Image + hand-drawn censor boxes; delegates geometry to :mod:`_manual`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scale = 1.0
        self._regions: list = []          # image-space (x1,y1,x2,y2)
        self._selected = -1
        self._drawing = False
        self._moving = False
        self._draw_start = None           # display-space
        self._draw_cur = None
        self._move_last = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- state -------------------------------------------------------

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._scale = fit_scale(pixmap.width(), pixmap.height(),
                                _MAX_CANVAS_W, _MAX_CANVAS_H)
        self.setFixedSize(max(1, int(pixmap.width() * self._scale)),
                          max(1, int(pixmap.height() * self._scale)))
        self.update()

    def image_size(self):
        return (self._pixmap.width(), self._pixmap.height()) if self._pixmap else (0, 0)

    def regions(self):
        return list(self._regions)

    def clear_regions(self):
        self._regions = []
        self._selected = -1
        self.update()

    # -- painting ----------------------------------------------------

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        if self._pixmap is not None:
            painter.drawPixmap(self.rect(), self._pixmap)
        for i, region in enumerate(self._regions):
            selected = i == self._selected
            x, y, w, h = to_display_rect(region, self._scale)
            painter.fillRect(x, y, w, h,
                             QColor(0, 120, 255, 90) if selected
                             else QColor(255, 0, 0, 70))
            painter.setPen(QPen(QColor(0, 120, 255) if selected
                                else QColor(255, 0, 0), 2))
            painter.drawRect(x, y, w, h)
        if self._drawing and self._draw_start and self._draw_cur:
            x0, y0 = self._draw_start
            x1, y1 = self._draw_cur
            painter.setPen(QPen(QColor(255, 200, 0), 2))
            painter.drawRect(int(min(x0, x1)), int(min(y0, y1)),
                             int(abs(x1 - x0)), int(abs(y1 - y0)))

    # -- mouse / keyboard -------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        pos = event.position()
        ix, iy = to_image_point(pos.x(), pos.y(), self._scale)
        if event.button() == Qt.MouseButton.RightButton:
            idx = region_at(self._regions, ix, iy)
            if idx >= 0:
                self._regions.pop(idx)
                self._selected = -1
                self.update()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            idx = region_at(self._regions, ix, iy)
            if idx >= 0:
                self._selected = idx
                self._moving = True
                self._move_last = (pos.x(), pos.y())
            else:
                self._selected = -1
                self._drawing = True
                self._draw_start = (pos.x(), pos.y())
                self._draw_cur = (pos.x(), pos.y())
            self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        pos = event.position()
        if self._drawing:
            self._draw_cur = (pos.x(), pos.y())
            self.update()
        elif self._moving and self._selected >= 0:
            last_x, last_y = self._move_last
            dx = (pos.x() - last_x) / (self._scale or 1.0)
            dy = (pos.y() - last_y) / (self._scale or 1.0)
            iw, ih = self.image_size()
            self._regions[self._selected] = clamp_region(
                move_region(self._regions[self._selected], dx, dy), iw, ih)
            self._move_last = (pos.x(), pos.y())
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        if self._drawing and self._draw_start and self._draw_cur:
            ix0, iy0 = to_image_point(*self._draw_start, self._scale)
            ix1, iy1 = to_image_point(*self._draw_cur, self._scale)
            iw, ih = self.image_size()
            region = clamp_region(normalize_rect(ix0, iy0, ix1, iy1), iw, ih)
            if is_valid_region(region):
                self._regions.append(region)
                self._selected = len(self._regions) - 1
        self._drawing = self._moving = False
        self._draw_start = self._draw_cur = self._move_last = None
        self.update()

    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        if (event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
                and self._selected >= 0):
            self._regions.pop(self._selected)
            self._selected = -1
            self.update()
        else:
            super().keyPressEvent(event)


class ManualReviewDialog(QDialog):
    """Draw / edit censor boxes over one image, then apply them."""

    def __init__(self, main_gui, image_path: str):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            self._lang.get("safety_review_manual_title", "Manual Review & Mosaic"))
        self._build_ui()
        self._load_image()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        info = QLabel(self._lang.get(
            "safety_review_manual_hint",
            "Drag to draw a censor box. Click one to select, drag to move, "
            "right-click or press Delete to remove it."))
        info.setWordWrap(True)
        layout.addWidget(info)

        self._canvas = _ManualCanvas()
        scroll = QScrollArea()
        scroll.setWidget(self._canvas)
        scroll.setWidgetResizable(False)
        layout.addWidget(scroll, 1)

        layout.addLayout(self._build_options_row())
        layout.addLayout(self._build_button_row())

    def _build_options_row(self):
        row = QHBoxLayout()
        self._style_combo = QComboBox()
        for label, data in (
            (self._lang.get("safety_review_style_mosaic", "Mosaic"), STYLE_MOSAIC),
            (self._lang.get("safety_review_style_blur", "Gaussian Blur"), STYLE_BLUR),
            (self._lang.get("safety_review_style_black", "Black Bar"), STYLE_BLACK),
        ):
            self._style_combo.addItem(label, data)
        row.addWidget(self._style_combo)

        self._shape_combo = QComboBox()
        self._shape_combo.addItem(
            self._lang.get("safety_review_shape_ellipse", "Ellipse (tighter)"),
            SHAPE_ELLIPSE)
        self._shape_combo.addItem(
            self._lang.get("safety_review_shape_rect", "Rectangle (whole box)"),
            SHAPE_RECT)
        row.addWidget(self._shape_combo)

        self._block_spin = QSpinBox()
        self._block_spin.setRange(2, 64)
        self._block_spin.setValue(DEFAULT_BLOCK_SIZE)
        row.addWidget(self._block_spin)

        self._overwrite_check = QCheckBox(
            self._lang.get("safety_review_overwrite_single",
                           "Overwrite original file"))
        row.addWidget(self._overwrite_check)
        row.addStretch()
        return row

    def _build_button_row(self):
        row = QHBoxLayout()
        clear_btn = QPushButton(self._lang.get("safety_review_clear", "Clear all"))
        clear_btn.clicked.connect(self._canvas.clear_regions)
        row.addWidget(clear_btn)
        row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        self._apply_btn = QPushButton(
            self._lang.get("safety_review_apply", "Apply"))
        self._apply_btn.clicked.connect(self._apply)
        row.addWidget(self._apply_btn)
        return row

    def _load_image(self):
        pixmap = _load_pixmap(self._image_path)
        if pixmap.isNull():
            self._apply_btn.setEnabled(False)
            return
        self._canvas.set_image(pixmap)

    def _output_path(self) -> str:
        if self._overwrite_check.isChecked():
            return self._image_path
        src = Path(self._image_path)
        return str(src.with_name(f"{src.stem}_censored{src.suffix}"))

    def _apply(self):
        regions = self._canvas.regions()
        if not regions:
            return
        try:
            _process_manual_image(
                self._image_path, self._output_path(), regions,
                self._block_spin.value(),
                style=self._style_combo.currentData(),
                shape=self._shape_combo.currentData())
        except Exception:
            logger.error("Manual censor apply failed", exc_info=True)
            return
        if self._overwrite_check.isChecked():
            from safety_review._dialogs import _reload_grid_or_deepzoom
            _reload_grid_or_deepzoom(self._gui)
        if hasattr(self._gui.main_window, "toast"):
            self._gui.main_window.toast.success(
                self._lang.get("safety_review_manual_done",
                               "Applied {count} censor region(s)").format(
                                   count=len(regions)))
        self.accept()
