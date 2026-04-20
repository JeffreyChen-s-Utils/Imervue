"""
Annotation dialog — macOS Preview Markup style image annotation.

Opens on a PIL image (from disk or the clipboard) and lets the user draw
rectangles, ellipses, lines, arrows, freehand strokes, text, mosaic, and
blur annotations on top. Save writes a flattened PNG/JPEG (destructive);
Save Project writes the annotations as JSON so they can be reloaded and
re-edited without losing layer information.

Layout
------
    +----------------------------------------------------+
    | [tool buttons] | [color] [width] | [undo] [redo]   |  <- QToolBar
    +----------------------------------------------------+
    |                                                    |
    |                 AnnotationCanvas                   |
    |                                                    |
    +----------------------------------------------------+
    |       [Project...] [Copy] [Save As] [Save]         |  <- bottom bar
    +----------------------------------------------------+
"""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Callable

import numpy as np
from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QImage, QKeySequence, QMouseEvent,
    QPainter, QPainterPath, QPen, QPolygonF, QUndoCommand, QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMenuBar, QMessageBox, QSizePolicy, QSlider, QSpinBox,
    QStatusBar, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from Imervue.gui.annotation_models import (
    ALL_BRUSHES, Annotation, AnnotationKind, AnnotationProject, bake,
)
from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

logger = logging.getLogger("Imervue.annotation")

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# Annotation kind discriminators — centralised so SonarQube S1192 is satisfied
# and subtle typos surface as NameError rather than silently mis-compare.
_KIND_FREEHAND = "freehand"
_KIND_TEXT = "text"
_KIND_MOSAIC = "mosaic"
_KIND_BLUR = "blur"
_KIND_LINE = "line"
_KIND_ARROW = "arrow"
_KIND_PEN = "pen"
_KIND_CROP = "crop"
_KIND_SELECT = "select"
_KIND_MOVE = "move"

_MODE_RGBA = "RGBA"
_QSS_PANEL_SECTION = "panelSection"

_LOAD_PROJECT_FALLBACK = "Load Project..."


# ---------------------------------------------------------------------------
# PIL <-> QImage helpers
# ---------------------------------------------------------------------------

def pil_to_qimage(img: Image.Image) -> QImage:
    """Convert a PIL Image to an owned QImage (RGBA8888)."""
    if img.mode != _MODE_RGBA:
        img = img.convert(_MODE_RGBA)
    arr = np.array(img)
    h, w = arr.shape[:2]
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    # .copy() detaches from the numpy buffer — otherwise the QImage dies
    # the moment `arr` goes out of scope.
    return qimg.copy()


def qimage_to_pil(qimg: QImage) -> Image.Image:
    """Convert a QImage to a PIL RGBA Image."""
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------------------
# Undo commands
# ---------------------------------------------------------------------------

class _AddAnnotationCommand(QUndoCommand):
    def __init__(self, canvas: AnnotationCanvas, annotation: Annotation):
        super().__init__("Add annotation")
        self._canvas = canvas
        self._ann = annotation

    def redo(self):
        self._canvas._annotations.append(self._ann)
        self._canvas._selected_id = self._ann.id
        self._canvas.update()

    def undo(self):
        self._canvas._annotations = [
            a for a in self._canvas._annotations if a.id != self._ann.id
        ]
        if self._canvas._selected_id == self._ann.id:
            self._canvas._selected_id = None
        self._canvas.update()


class _DeleteAnnotationCommand(QUndoCommand):
    def __init__(self, canvas: AnnotationCanvas, annotation: Annotation):
        super().__init__("Delete annotation")
        self._canvas = canvas
        self._ann = annotation
        self._index = -1

    def redo(self):
        self._index = next(
            (i for i, a in enumerate(self._canvas._annotations) if a.id == self._ann.id),
            -1,
        )
        if self._index >= 0:
            self._canvas._annotations.pop(self._index)
        if self._canvas._selected_id == self._ann.id:
            self._canvas._selected_id = None
        self._canvas.update()

    def undo(self):
        if self._index < 0:
            self._canvas._annotations.append(self._ann)
        else:
            self._canvas._annotations.insert(self._index, self._ann)
        self._canvas.update()


class _BakeDestructiveCommand(QUndoCommand):
    """Destructively bake a mosaic/blur region into the canvas base image.

    We snapshot the full PIL image on both sides so undo/redo can swap
    them. Mosaic/blur annotations aren't kept as Annotation objects after
    this command runs — they're burned into the pixels, just like a save
    would do. The save-to-disk step still happens separately via the
    Save button, so the user can still bail out by closing without saving.
    """

    def __init__(
        self,
        canvas: AnnotationCanvas,
        old_img: Image.Image,
        new_img: Image.Image,
        text: str = "Apply mosaic/blur",
    ):
        super().__init__(text)
        self._canvas = canvas
        self._old = old_img
        self._new = new_img

    def redo(self):
        self._canvas._set_base_image(self._new)

    def undo(self):
        self._canvas._set_base_image(self._old)


class _ModifyAnnotationCommand(QUndoCommand):
    def __init__(
        self,
        canvas: AnnotationCanvas,
        annotation_id: str,
        old_points: list[tuple[int, int]],
        new_points: list[tuple[int, int]],
    ):
        super().__init__("Move/resize annotation")
        self._canvas = canvas
        self._id = annotation_id
        self._old = [tuple(p) for p in old_points]
        self._new = [tuple(p) for p in new_points]

    def _set(self, pts: list[tuple[int, int]]) -> None:
        for a in self._canvas._annotations:
            if a.id == self._id:
                a.points = [tuple(p) for p in pts]
                break
        self._canvas.update()

    def redo(self):
        self._set(self._new)

    def undo(self):
        self._set(self._old)


# ---------------------------------------------------------------------------
# Canvas widget
# ---------------------------------------------------------------------------

_HANDLE_SIZE = 8  # pixels (screen space)


class AnnotationCanvas(QWidget):
    """Interactive canvas that renders a PIL base image + annotation overlay.

    All Annotation.points are stored in image coordinates; the canvas maps
    between image coords and widget coords via ``_display_rect``.
    """

    annotation_changed = Signal()
    # Emitted whenever the mouse moves over the canvas, in image coordinates.
    # Used by the dialog's status bar to show a live cursor readout just like
    # a professional editor does (Photoshop / GIMP / Krita all have this).
    cursor_image_pos = Signal(int, int)
    # Emitted when the active tool changes so the status bar / properties
    # panel can mirror it without reaching into private state.
    tool_changed = Signal(str)
    # Emitted when the user presses Left/Right arrow to switch images.
    # The int argument is the direction: -1 for previous, +1 for next.
    navigate_image = Signal(int)

    def __init__(self, base: Image.Image, undo_stack: QUndoStack, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)

        self._base = base if base.mode == "RGBA" else base.convert("RGBA")
        self._base_qimg = pil_to_qimage(self._base)
        self._annotations: list[Annotation] = []
        self._undo_stack = undo_stack

        # Tool state
        self._tool: str = "select"
        self._color: tuple[int, int, int, int] = (255, 0, 0, 255)
        self._stroke_width: int = 3
        # Freehand brush parameters — only meaningful when ``_tool`` is
        # "freehand" but we keep them on the canvas so the Brush section in
        # the properties panel can flip them at any time.
        self._brush_type: str = "pen"
        self._brush_opacity: int = 100
        self._brush_spacing: int = 8
        self._font_family: str = ""
        self._font_size: int = 24
        # 馬賽克/模糊使用者上次選的強度 — 下次 prompt 時當預設值，省得
        # 每次都從頭調整。
        self._last_block_size: int = 4
        self._last_blur_radius: int = 4
        # 馬賽克/模糊強度對話框的 live preview — 把實際套用後的那一小塊
        # 畫到 base image 上面，所以使用者調 slider 的時候可以即時看到
        # 效果。None 表示沒有預覽。
        self._preview_qimg: QImage | None = None
        self._preview_rect_image: tuple[int, int, int, int] | None = None

        # Drawing / drag state
        self._drawing: Annotation | None = None
        self._selected_id: str | None = None
        self._drag_mode: str | None = None  # "move" or "resize_<handle>"
        self._drag_start_image: tuple[int, int] | None = None
        self._drag_orig_points: list[tuple[int, int]] | None = None

        # Crop tool state
        self._crop_rect: tuple[int, int, int, int] | None = None  # x, y, w, h in image coords
        self._crop_ratio: tuple[int, int] = (0, 0)  # zero zero means freeform ratio
        self._crop_dragging: bool = False
        self._crop_drag_start: tuple[int, int] | None = None
        self._crop_drag_handle: str | None = None  # none for new, or move, or nw..w handle
        self._crop_drag_orig: tuple[int, int, int, int] | None = None

        # Inline text editor
        self._text_edit: QLineEdit | None = None
        self._text_anchor_image: tuple[int, int] | None = None

    # ---------- Public API ----------

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self._selected_id = None
        self._cancel_text_edit()
        self.tool_changed.emit(tool)
        self.update()

    def current_tool(self) -> str:
        return self._tool

    def set_color(self, color: tuple[int, int, int, int]) -> None:
        self._color = color
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id:
                    a.color = color
            self.update()

    def set_stroke_width(self, w: int) -> None:
        self._stroke_width = max(1, w)
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id:
                    a.stroke_width = self._stroke_width
            self.update()

    def set_brush_type(self, brush: str) -> None:
        if brush not in ALL_BRUSHES:
            return
        self._brush_type = brush
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id and a.kind == _KIND_FREEHAND:
                    a.brush_type = brush  # type: ignore[assignment]
            self.update()

    def set_brush_opacity(self, opacity: int) -> None:
        self._brush_opacity = max(0, min(100, int(opacity)))
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id and a.kind == _KIND_FREEHAND:
                    a.opacity = self._brush_opacity
            self.update()

    def set_brush_spacing(self, spacing: int) -> None:
        self._brush_spacing = max(1, int(spacing))
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id and a.kind == _KIND_FREEHAND:
                    a.spacing = self._brush_spacing
            self.update()

    def set_font_family(self, family: str) -> None:
        self._font_family = family
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id and a.kind == _KIND_TEXT:
                    a.font_family = family
            self.update()

    def set_font_size(self, size: int) -> None:
        self._font_size = max(6, size)
        if self._selected_id is not None:
            for a in self._annotations:
                if a.id == self._selected_id and a.kind == _KIND_TEXT:
                    a.font_size = self._font_size
            self.update()

    def current_font_family(self) -> str:
        return self._font_family

    def current_font_size(self) -> int:
        return self._font_size

    # ---------- Crop API ----------

    def set_crop_ratio(self, rw: int, rh: int) -> None:
        self._crop_ratio = (rw, rh)
        if self._crop_rect is not None and rw > 0 and rh > 0:
            self._enforce_crop_ratio()
            self.update()

    def get_crop_rect(self) -> tuple[int, int, int, int] | None:
        return self._crop_rect

    def clear_crop(self) -> None:
        self._crop_rect = None
        self._crop_dragging = False
        self._crop_drag_handle = None
        self.update()

    def _enforce_crop_ratio(self) -> None:
        """Adjust crop rect to match the current aspect ratio, anchored at center."""
        if self._crop_rect is None:
            return
        rw, rh = self._crop_ratio
        if rw <= 0 or rh <= 0:
            return
        x, y, w, h = self._crop_rect
        cx, cy = x + w / 2, y + h / 2
        target = rw / rh
        current = w / max(1, h)
        if current > target:
            # too wide → shrink width
            new_w = int(h * target)
            new_h = h
        else:
            new_w = w
            new_h = int(w / target)
        nx = max(0, min(self._base.width - new_w, int(cx - new_w / 2)))
        ny = max(0, min(self._base.height - new_h, int(cy - new_h / 2)))
        self._crop_rect = (nx, ny, new_w, new_h)

    def current_brush_type(self) -> str:
        return self._brush_type

    def current_brush_opacity(self) -> int:
        return self._brush_opacity

    def current_brush_spacing(self) -> int:
        return self._brush_spacing

    def get_base_pil(self) -> Image.Image:
        return self._base

    def _set_base_image(self, img: Image.Image) -> None:
        """Swap the underlying PIL image (used by _BakeDestructiveCommand
        for undo/redo of mosaic/blur bakes). Callers must own ``img`` —
        we don't copy it here.
        """
        self._base = img if img.mode == "RGBA" else img.convert(_MODE_RGBA)
        self._base_qimg = pil_to_qimage(self._base)
        self.update()

    def get_annotations(self) -> list[Annotation]:
        return list(self._annotations)

    def set_annotations(self, anns: list[Annotation]) -> None:
        self._annotations = list(anns)
        self._selected_id = None
        self._undo_stack.clear()
        self.update()

    # ---------- Coordinate mapping ----------

    def _display_rect(self) -> QRectF:
        bw, bh = self._base.width, self._base.height
        cw, ch = self.width(), self.height()
        if bw == 0 or bh == 0 or cw == 0 or ch == 0:
            return QRectF(0, 0, 0, 0)
        scale = min(cw / bw, ch / bh)
        dw, dh = bw * scale, bh * scale
        return QRectF((cw - dw) / 2, (ch - dh) / 2, dw, dh)

    def _screen_to_image(self, x: float, y: float) -> tuple[int, int]:
        rect = self._display_rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return (0, 0)
        ix = (x - rect.x()) * self._base.width / rect.width()
        iy = (y - rect.y()) * self._base.height / rect.height()
        return (int(round(ix)), int(round(iy)))

    def _image_to_screen(self, ix: float, iy: float) -> QPointF:
        rect = self._display_rect()
        if self._base.width == 0 or self._base.height == 0:
            return QPointF(0, 0)
        sx = rect.x() + ix * rect.width() / self._base.width
        sy = rect.y() + iy * rect.height() / self._base.height
        return QPointF(sx, sy)

    # ---------- Painting ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        rect = self._display_rect()
        if rect.width() > 0:
            painter.drawImage(rect, self._base_qimg)

            # Render annotations in image coordinates via transform
            painter.save()
            painter.translate(rect.x(), rect.y())
            painter.scale(
                rect.width() / self._base.width,
                rect.height() / self._base.height,
            )
            # Live preview for mosaic/blur strength dialog — paint the
            # baked region directly over the base so the user can see the
            # effect as they drag the slider.
            if (self._preview_qimg is not None
                    and self._preview_rect_image is not None):
                px, py, pw, ph = self._preview_rect_image
                painter.drawImage(QRectF(px, py, pw, ph), self._preview_qimg)
            for ann in self._annotations:
                self._draw_annotation_qt(painter, ann)
            if self._drawing is not None:
                self._draw_annotation_qt(painter, self._drawing)
            painter.restore()

        if self._selected_id is not None:
            sel = self._find(self._selected_id)
            if sel is not None:
                self._draw_selection(painter, sel)

        # Crop overlay: dim outside, dashed border, handles
        if self._tool == _KIND_CROP and self._crop_rect is not None and rect.width() > 0:
            cx, cy, cw, ch = self._crop_rect
            tl = self._image_to_screen(cx, cy)
            br = self._image_to_screen(cx + cw, cy + ch)
            crop_screen = QRectF(tl, br).normalized()
            # Dim outside region
            dim = QColor(0, 0, 0, 140)
            # Top
            painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(),
                                    crop_screen.top() - rect.top()), dim)
            # Bottom
            painter.fillRect(QRectF(rect.left(), crop_screen.bottom(),
                                    rect.width(), rect.bottom() - crop_screen.bottom()), dim)
            # Left
            painter.fillRect(QRectF(rect.left(), crop_screen.top(),
                                    crop_screen.left() - rect.left(),
                                    crop_screen.height()), dim)
            # Right
            painter.fillRect(QRectF(crop_screen.right(), crop_screen.top(),
                                    rect.right() - crop_screen.right(),
                                    crop_screen.height()), dim)
            # Dashed border
            crop_pen = QPen(QColor(255, 255, 255))
            crop_pen.setWidthF(1.5)
            crop_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(crop_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(crop_screen)
            # Rule of thirds guidelines
            thirds_pen = QPen(QColor(255, 255, 255, 80))
            thirds_pen.setWidthF(0.5)
            painter.setPen(thirds_pen)
            for i in range(1, 3):
                tx = crop_screen.left() + crop_screen.width() * i / 3
                ty = crop_screen.top() + crop_screen.height() * i / 3
                painter.drawLine(QPointF(tx, crop_screen.top()),
                                 QPointF(tx, crop_screen.bottom()))
                painter.drawLine(QPointF(crop_screen.left(), ty),
                                 QPointF(crop_screen.right(), ty))
            # Resize handles
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            h = _HANDLE_SIZE
            for hx, hy in self._handle_positions(crop_screen):
                painter.drawRect(QRectF(hx - h / 2, hy - h / 2, h, h))
            # Size label
            size_text = f"{cw} x {ch}"
            painter.setPen(QPen(QColor(255, 255, 255)))
            label_font = QFont()
            label_font.setPixelSize(12)
            painter.setFont(label_font)
            painter.drawText(
                QPointF(crop_screen.left() + 4, crop_screen.top() - 4),
                size_text)

        painter.end()

    def _draw_annotation_qt(self, painter: QPainter, ann: Annotation) -> None:
        color = QColor(*ann.color)
        pen = QPen(color)
        pen.setWidthF(ann.stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(color) if ann.filled else Qt.BrushStyle.NoBrush)

        if ann.kind == "rect":
            x1, y1, x2, y2 = ann.bounding_box()
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        elif ann.kind == "ellipse":
            x1, y1, x2, y2 = ann.bounding_box()
            painter.drawEllipse(QRectF(x1, y1, x2 - x1, y2 - y1))
        elif ann.kind == _KIND_LINE:
            if len(ann.points) >= 2:
                painter.drawLine(QPointF(*ann.points[0]),
                                 QPointF(*ann.points[-1]))
        elif ann.kind == _KIND_ARROW:
            self._draw_arrow_qt(painter, ann)
        elif ann.kind == _KIND_FREEHAND:
            if len(ann.points) >= 2:
                self._draw_freehand_qt(painter, ann)
        elif ann.kind == _KIND_TEXT:
            if ann.text and ann.points:
                font = QFont(ann.font_family) if ann.font_family else QFont()
                font.setPixelSize(max(6, ann.font_size))
                painter.setFont(font)
                painter.setPen(QPen(color))
                painter.drawText(QPointF(*ann.points[0]), ann.text)
        elif ann.kind in (_KIND_MOSAIC, _KIND_BLUR):
            # Preview: dashed outline + translucent fill so the user sees the
            # region they're about to pixelate/blur. The destructive effect
            # only happens at bake() time.
            preview_pen = QPen(color)
            preview_pen.setWidthF(2)
            preview_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(preview_pen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            x1, y1, x2, y2 = ann.bounding_box()
            region = QRectF(x1, y1, x2 - x1, y2 - y1)
            painter.drawRect(region)
            label = ann.kind
            label_font = QFont()
            label_font.setPixelSize(max(12, int(min(region.width(), region.height()) / 8)))
            painter.setFont(label_font)
            painter.drawText(region, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_arrow_qt(self, painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) < 2:
            return
        sx, sy = ann.points[0]
        ex, ey = ann.points[-1]
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        head_len = max(10, ann.stroke_width * 5)
        head_half = max(6, ann.stroke_width * 3)
        ux, uy = dx / length, dy / length
        line_end = QPointF(ex - ux * head_len * 0.6, ey - uy * head_len * 0.6)
        painter.drawLine(QPointF(sx, sy), line_end)
        base_center = (ex - ux * head_len, ey - uy * head_len)
        px, py = -uy, ux
        poly = QPolygonF([
            QPointF(ex, ey),
            QPointF(base_center[0] + px * head_half, base_center[1] + py * head_half),
            QPointF(base_center[0] - px * head_half, base_center[1] - py * head_half),
        ])
        painter.setBrush(QBrush(QColor(*ann.color)))
        painter.drawPolygon(poly)

    # (alpha_scale, width_factor) — multiplier applied to stroke_width.
    _BRUSH_PRESETS = {
        "marker":      (0.7, 1.8),
        "pencil":      (0.85, 0.5),
        "highlighter": (0.35, 3.0),
        "watercolor":  (0.2, 2.5),
        "crayon":      (0.8, 1.5),
        "pen":         (1.0, 1.0),
    }

    def _draw_freehand_qt(self, painter: QPainter, ann: Annotation) -> None:
        """Live-preview counterpart to PIL ``_draw_freehand`` — mirrors the
        brush styles so what the user sees while dragging matches what
        ``bake()`` will produce on save.
        """
        brush = getattr(ann, "brush_type", "pen")
        opacity = max(0, min(100, int(getattr(ann, "opacity", 100))))

        # Brush styles that have their own dedicated renderer.
        if brush == "spray":
            self._draw_freehand_spray_qt(painter, ann, opacity)
            return
        if brush == "calligraphy":
            self._draw_freehand_calligraphy_qt(painter, ann, opacity)
            return
        if brush == "charcoal":
            self._draw_freehand_charcoal_qt(painter, ann, opacity)
            return

        alpha_scale, width_factor = self._BRUSH_PRESETS.get(
            brush, self._BRUSH_PRESETS["pen"]
        )
        width = max(1, int(ann.stroke_width * width_factor))

        r, g, b, a = ann.color
        final_alpha = int(a * alpha_scale * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if brush == "watercolor":
            # Draw 3 passes with slight random offset for wet-edge look
            import random as _random
            rng = _random.Random(hash(ann.id) & 0xFFFFFFFF)
            for _ in range(3):
                path = QPainterPath()
                pts = ann.points
                x0, y0 = pts[0]
                path.moveTo(x0 + rng.gauss(0, width * 0.15),
                            y0 + rng.gauss(0, width * 0.15))
                for px, py in pts[1:]:
                    path.lineTo(px + rng.gauss(0, width * 0.15),
                                py + rng.gauss(0, width * 0.15))
                painter.drawPath(path)
        elif brush == "crayon":
            # Draw 3 thin jittered lines for waxy texture
            import random as _random
            rng = _random.Random(hash(ann.id) & 0xFFFFFFFF)
            for offset in range(3):
                w = max(1, width - offset)
                pen2 = QPen(color)
                pen2.setWidthF(w)
                pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen2)
                path = QPainterPath()
                pts = ann.points
                path.moveTo(pts[0][0] + rng.uniform(-1, 1),
                            pts[0][1] + rng.uniform(-1, 1))
                for px, py in pts[1:]:
                    path.lineTo(px + rng.uniform(-1, 1),
                                py + rng.uniform(-1, 1))
                painter.drawPath(path)
        else:
            path = QPainterPath()
            path.moveTo(*ann.points[0])
            for p in ann.points[1:]:
                path.lineTo(*p)
            painter.drawPath(path)

    def _draw_freehand_spray_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        import random as _random
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        radius = max(1, ann.stroke_width)
        spread = max(2, ann.stroke_width * 3)
        spacing = max(1, int(ann.spacing))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))

        rng = _random.Random(hash(ann.id) & 0xFFFFFFFF)
        pts = ann.points
        samples: list[tuple[float, float]] = [
            (float(pts[0][0]), float(pts[0][1]))
        ]
        accumulated = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len <= 0:
                continue
            ux, uy = (x2 - x1) / seg_len, (y2 - y1) / seg_len
            remaining = seg_len
            while accumulated + remaining >= spacing:
                step = spacing - accumulated
                cx = x1 + ux * (seg_len - remaining + step)
                cy = y1 + uy * (seg_len - remaining + step)
                samples.append((cx, cy))
                remaining -= step
                accumulated = 0.0
            accumulated += remaining

        dots_per_sample = max(4, ann.stroke_width * 2)
        for cx, cy in samples:
            for _ in range(dots_per_sample):
                while True:
                    ox = rng.uniform(-spread, spread)
                    oy = rng.uniform(-spread, spread)
                    if ox * ox + oy * oy <= spread * spread:
                        break
                painter.drawEllipse(
                    QRectF(cx + ox - radius / 2, cy + oy - radius / 2,
                           radius, radius)
                )

    def _draw_freehand_calligraphy_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        """Calligraphy: variable width based on stroke direction."""
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        base_w = max(1, ann.stroke_width)
        nib_angle = math.pi / 4
        cos_a, sin_a = math.cos(nib_angle), math.sin(nib_angle)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pts = ann.points
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            dx, dy = x2 - x1, y2 - y1
            seg_len = math.hypot(dx, dy)
            if seg_len < 0.5:
                continue
            ux, uy = dx / seg_len, dy / seg_len
            proj = abs(ux * cos_a + uy * sin_a)
            w = max(1, int(base_w * (0.3 + 0.7 * proj)))
            pen = QPen(color)
            pen.setWidthF(w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_freehand_charcoal_qt(
        self, painter: QPainter, ann: Annotation, opacity: int
    ) -> None:
        """Charcoal: rough textured stroke with scattered dots."""
        import random as _random
        r, g, b, a = ann.color
        final_alpha = int(a * opacity / 100)
        color = QColor(r, g, b, final_alpha)
        width = max(1, int(ann.stroke_width * 1.2))
        rng = _random.Random(hash(ann.id) & 0xFFFFFFFF)
        # Main stroke
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(*ann.points[0])
        for p in ann.points[1:]:
            path.lineTo(*p)
        painter.drawPath(path)
        # Scatter texture dots
        spread = max(2, width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        for x, y in ann.points[::3]:
            for _ in range(2):
                ox = rng.gauss(0, spread * 0.5)
                oy = rng.gauss(0, spread * 0.5)
                r2 = max(0.5, width * 0.3)
                painter.drawEllipse(QRectF(x + ox - r2, y + oy - r2, r2 * 2, r2 * 2))

    def _draw_selection(self, painter: QPainter, ann: Annotation) -> None:
        if ann.kind == _KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(ann)
        else:
            x1, y1, x2, y2 = ann.bounding_box()
        top_left = self._image_to_screen(x1, y1)
        bottom_right = self._image_to_screen(x2, y2)
        sel_rect = QRectF(top_left, bottom_right)

        pen = QPen(QColor(0, 150, 255))
        pen.setWidthF(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sel_rect)

        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 150, 255), 1))
        h = _HANDLE_SIZE
        for hx, hy in self._handle_positions(sel_rect):
            painter.drawRect(QRectF(hx - h / 2, hy - h / 2, h, h))

    @staticmethod
    def _handle_positions(r: QRectF) -> list[tuple[float, float]]:
        cx = (r.left() + r.right()) / 2
        cy = (r.top() + r.bottom()) / 2
        return [
            (r.left(), r.top()),      # nw
            (cx, r.top()),            # n
            (r.right(), r.top()),     # ne
            (r.right(), cy),          # e
            (r.right(), r.bottom()),  # se
            (cx, r.bottom()),         # s
            (r.left(), r.bottom()),   # sw
            (r.left(), cy),           # w
        ]

    _HANDLE_NAMES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")

    # ---------- Hit testing ----------

    def _find(self, ann_id: str) -> Annotation | None:
        for a in self._annotations:
            if a.id == ann_id:
                return a
        return None

    def _hit_handle(self, pt: QPointF) -> str | None:
        if self._selected_id is None:
            return None
        sel = self._find(self._selected_id)
        if sel is None:
            return None
        if sel.kind == _KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(sel)
        else:
            x1, y1, x2, y2 = sel.bounding_box()
        sel_rect = QRectF(
            self._image_to_screen(x1, y1),
            self._image_to_screen(x2, y2),
        )
        h = _HANDLE_SIZE
        for name, (hx, hy) in zip(
            self._HANDLE_NAMES, self._handle_positions(sel_rect), strict=False,
        ):
            box = QRectF(hx - h, hy - h, h * 2, h * 2)
            if box.contains(pt):
                return name
        return None

    def _text_bounding_box(self, ann: Annotation) -> tuple[int, int, int, int]:
        """Compute (x1, y1, x2, y2) for a text annotation using QFontMetrics."""
        if not ann.text or not ann.points:
            return ann.bounding_box()
        from PySide6.QtGui import QFontMetrics
        font = QFont(ann.font_family) if ann.font_family else QFont()
        font.setPixelSize(max(6, ann.font_size))
        fm = QFontMetrics(font)
        rect = fm.boundingRect(ann.text)
        ax, ay = ann.points[0]
        # QFontMetrics bounding rect: x offset can be negative, y is above baseline
        x1 = ax + rect.x()
        y1 = ay + rect.y()
        x2 = x1 + rect.width()
        y2 = y1 + rect.height()
        return (x1, y1, x2, y2)

    def _hit_annotation(self, pt: QPointF) -> Annotation | None:
        """Find the topmost annotation under ``pt`` (widget coords).

        Uses bounding-box hit for shape annotations and segment-distance
        hit for line-like annotations — a diagonal line's bounding box can
        be huge, and picking anywhere inside it would make selection feel
        broken.
        """
        ix, iy = self._screen_to_image(pt.x(), pt.y())
        for a in reversed(self._annotations):  # topmost first
            tol = max(5, a.stroke_width + 2)
            if a.kind in ("line", "arrow") and len(a.points) >= 2:
                if _point_segment_distance(
                    ix, iy, a.points[0], a.points[-1]
                ) <= tol:
                    return a
                continue
            if a.kind == _KIND_FREEHAND and len(a.points) >= 2:
                hit = False
                for p, q in zip(a.points, a.points[1:], strict=False):
                    if _point_segment_distance(ix, iy, p, q) <= tol:
                        hit = True
                        break
                if hit:
                    return a
                continue
            if a.kind == _KIND_TEXT:
                x1, y1, x2, y2 = self._text_bounding_box(a)
            else:
                x1, y1, x2, y2 = a.bounding_box()
            if x1 - tol <= ix <= x2 + tol and y1 - tol <= iy <= y2 + tol:
                return a
        return None

    # ---------- Mouse events ----------

    def _crop_hit_handle(self, pt: QPointF) -> str | None:
        """Check if pt hits a handle on the current crop rect."""
        if self._crop_rect is None:
            return None
        cx, cy, cw, ch = self._crop_rect
        crop_screen = QRectF(
            self._image_to_screen(cx, cy),
            self._image_to_screen(cx + cw, cy + ch),
        ).normalized()
        h = _HANDLE_SIZE
        for name, (hx, hy) in zip(
            self._HANDLE_NAMES, self._handle_positions(crop_screen), strict=False,
        ):
            box = QRectF(hx - h, hy - h, h * 2, h * 2)
            if box.contains(pt):
                return name
        # Inside crop rect = move
        if crop_screen.contains(pt):
            return _KIND_MOVE
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = event.position()
        ix, iy = self._screen_to_image(pt.x(), pt.y())

        # --- Crop tool ---
        if self._tool == _KIND_CROP:
            handle = self._crop_hit_handle(pt) if self._crop_rect else None
            if handle is not None:
                self._crop_dragging = True
                self._crop_drag_start = (ix, iy)
                self._crop_drag_handle = handle
                self._crop_drag_orig = self._crop_rect
                return
            # Start new crop
            self._crop_rect = (ix, iy, 0, 0)
            self._crop_dragging = True
            self._crop_drag_start = (ix, iy)
            self._crop_drag_handle = None  # new crop
            self._crop_drag_orig = None
            return

        if self._tool == _KIND_SELECT:
            handle = self._hit_handle(pt)
            if handle is not None:
                sel = self._find(self._selected_id)
                if sel is not None:
                    self._drag_mode = f"resize_{handle}"
                    self._drag_start_image = (ix, iy)
                    self._drag_orig_points = list(sel.points)
                    return
            hit = self._hit_annotation(pt)
            if hit is not None:
                self._selected_id = hit.id
                self._drag_mode = _KIND_MOVE
                self._drag_start_image = (ix, iy)
                self._drag_orig_points = list(hit.points)
                self.update()
                return
            self._selected_id = None
            self.update()
            return

        if self._tool == _KIND_TEXT:
            self._begin_text_edit(ix, iy)
            return

        # Shape / freehand tools
        kind: AnnotationKind = self._tool  # type: ignore[assignment]
        if kind == "freehand":
            self._drawing = Annotation(
                kind=_KIND_FREEHAND,
                points=[(ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
                brush_type=self._brush_type,  # type: ignore[arg-type]
                opacity=self._brush_opacity,
                spacing=self._brush_spacing,
            )
        else:
            self._drawing = Annotation(
                kind=kind,
                points=[(ix, iy), (ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
            )
        self.update()

    def _crop_drag_new_rect(self, sx: int, sy: int, ix: int, iy: int) -> None:
        x1, y1 = max(0, min(sx, ix)), max(0, min(sy, iy))
        x2 = min(self._base.width, max(sx, ix))
        y2 = min(self._base.height, max(sy, iy))
        self._crop_rect = (x1, y1, x2 - x1, y2 - y1)
        rw, rh = self._crop_ratio
        if rw > 0 and rh > 0:
            self._enforce_crop_ratio()

    def _crop_drag_move(self, sx: int, sy: int, ix: int, iy: int) -> None:
        ox, oy, ow, oh = self._crop_drag_orig
        dx, dy = ix - sx, iy - sy
        nx = max(0, min(self._base.width - ow, ox + dx))
        ny = max(0, min(self._base.height - oh, oy + dy))
        self._crop_rect = (nx, ny, ow, oh)

    def _crop_drag_resize(self, sx: int, sy: int, ix: int, iy: int) -> None:
        ox, oy, ow, oh = self._crop_drag_orig
        dx, dy = ix - sx, iy - sy
        h = self._crop_drag_handle
        nx, ny, nw, nh = ox, oy, ow, oh
        if "w" in h:
            nx, nw = ox + dx, ow - dx
        if "e" in h:
            nw = ow + dx
        if "n" in h:
            ny, nh = oy + dy, oh - dy
        if "s" in h:
            nh = oh + dy
        nw, nh = max(nw, 1), max(nh, 1)
        nx, ny = max(0, nx), max(0, ny)
        nw = min(self._base.width - nx, nw)
        nh = min(self._base.height - ny, nh)
        self._crop_rect = (int(nx), int(ny), int(nw), int(nh))
        rw, rh = self._crop_ratio
        if rw > 0 and rh > 0:
            self._enforce_crop_ratio()

    def _handle_crop_move(self, pt, ix: int, iy: int) -> None:
        if self._crop_dragging and self._crop_drag_start is not None:
            sx, sy = self._crop_drag_start
            if self._crop_drag_handle is None:
                self._crop_drag_new_rect(sx, sy, ix, iy)
            elif self._crop_drag_handle == _KIND_MOVE and self._crop_drag_orig:
                self._crop_drag_move(sx, sy, ix, iy)
            elif self._crop_drag_orig:
                self._crop_drag_resize(sx, sy, ix, iy)
            self.update()
            return
        handle = self._crop_hit_handle(pt) if self._crop_rect else None
        if handle is not None and handle != _KIND_MOVE:
            self.setCursor(_handle_cursor(handle))
        elif handle == _KIND_MOVE:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _update_select_cursor(self, pt) -> None:
        handle = self._hit_handle(pt)
        if handle is not None:
            self.setCursor(_handle_cursor(handle))
        elif self._hit_annotation(pt) is not None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _drag_selected_annotation(self, ix: int, iy: int) -> None:
        sel = self._find(self._selected_id or "")
        if sel is None:
            return
        sx, sy = self._drag_start_image  # type: ignore[misc]
        dx, dy = ix - sx, iy - sy
        if self._drag_mode == _KIND_MOVE:
            sel.points = [(p[0] + dx, p[1] + dy) for p in self._drag_orig_points]
        elif self._drag_mode.startswith("resize_"):
            handle = self._drag_mode.split("_", 1)[1]
            sel.points = self._resize_points(
                self._drag_orig_points, handle, dx, dy
            )
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pt = event.position()
        ix, iy = self._screen_to_image(pt.x(), pt.y())
        self.cursor_image_pos.emit(ix, iy)

        if self._tool == _KIND_CROP:
            self._handle_crop_move(pt, ix, iy)
            return

        if self._tool == _KIND_SELECT and self._drag_mode is None:
            self._update_select_cursor(pt)

        if self._drag_mode is not None and self._drag_orig_points is not None:
            self._drag_selected_annotation(ix, iy)
            return

        if self._drawing is not None:
            if self._drawing.kind == _KIND_FREEHAND:
                self._drawing.points.append((ix, iy))
            else:
                self._drawing.points[-1] = (ix, iy)
            self.update()

    def _finish_crop_drag(self) -> None:
        self._crop_dragging = False
        self._crop_drag_start = None
        self._crop_drag_handle = None
        self._crop_drag_orig = None
        if self._crop_rect is not None:
            _, _, cw, ch = self._crop_rect
            if cw < 2 or ch < 2:
                self._crop_rect = None
        self.update()

    def _finish_annotation_drag(self) -> None:
        sel = self._find(self._selected_id or "")
        if sel is not None:
            new_points = list(sel.points)
            if new_points != self._drag_orig_points:
                # Revert then push command so redo/undo both go through it
                sel.points = [tuple(p) for p in self._drag_orig_points]
                cmd = _ModifyAnnotationCommand(
                    self, sel.id, self._drag_orig_points, new_points
                )
                self._undo_stack.push(cmd)
        self._drag_mode = None
        self._drag_orig_points = None
        self._drag_start_image = None
        self.annotation_changed.emit()

    def _is_degenerate(self, drawing: Annotation) -> bool:
        if drawing.kind == _KIND_FREEHAND:
            return len(drawing.points) < 2
        x1, y1 = drawing.points[0]
        x2, y2 = drawing.points[-1]
        return abs(x2 - x1) < 2 and abs(y2 - y1) < 2

    def _finish_drawing(self) -> None:
        drawing = self._drawing
        self._drawing = None
        if self._is_degenerate(drawing):
            self.update()
            return
        # 馬賽克/模糊：框選完立刻問使用者要多強，確認後把像素烤進 base
        # image（不存檔）。取消就什麼事也不做。
        if drawing.kind in (_KIND_MOSAIC, _KIND_BLUR):
            if self._prompt_destructive_strength(drawing):
                self.annotation_changed.emit()
            else:
                self.update()
            return
        cmd = _AddAnnotationCommand(self, drawing)
        self._undo_stack.push(cmd)
        self.annotation_changed.emit()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._tool == _KIND_CROP and self._crop_dragging:
            self._finish_crop_drag()
            return
        if self._drag_mode is not None and self._drag_orig_points is not None:
            self._finish_annotation_drag()
            return
        if self._drawing is not None:
            self._finish_drawing()

    def _prompt_destructive_strength(self, ann: Annotation) -> bool:
        """Ask the user for mosaic block size / blur radius with a live
        preview of the effect painted on the canvas.

        The dialog is positioned away from the annotation's screen rect so
        it doesn't cover the region the user is previewing. Returns True
        if the user confirmed, False if they cancelled (the caller should
        then discard the annotation).
        """
        lang = language_wrapper.language_word_dict
        if ann.kind == _KIND_MOSAIC:
            title = lang.get("annotation_mosaic_prompt_title", "Mosaic strength")
            label_text = lang.get(
                "annotation_mosaic_prompt_label",
                "Block size (pixels):",
            )
            initial = self._last_block_size
            minv, maxv = 2, 200
        elif ann.kind == _KIND_BLUR:
            title = lang.get("annotation_blur_prompt_title", "Blur strength")
            label_text = lang.get(
                "annotation_blur_prompt_label",
                "Gaussian radius (pixels):",
            )
            initial = self._last_blur_radius
            minv, maxv = 1, 200
        else:
            return True

        # Keep the dashed-outline preview visible during the dialog —
        # _drawing was nulled in mouseReleaseEvent, restore it.
        self._drawing = ann

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(label_text))

        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal, dlg)
        slider.setRange(minv, maxv)
        slider.setValue(initial)
        spin = QSpinBox(dlg)
        spin.setRange(minv, maxv)
        spin.setValue(initial)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        layout.addLayout(row)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dlg,
        )
        bbox.accepted.connect(dlg.accept)
        bbox.rejected.connect(dlg.reject)
        layout.addWidget(bbox)

        def apply_value(val: int) -> None:
            if ann.kind == _KIND_MOSAIC:
                ann.block_size = int(val)
            else:
                ann.blur_radius = int(val)
            self._update_destructive_preview(ann)

        def on_slider(v: int) -> None:
            spin.blockSignals(True)
            spin.setValue(v)
            spin.blockSignals(False)
            apply_value(v)

        def on_spin(v: int) -> None:
            slider.blockSignals(True)
            slider.setValue(v)
            slider.blockSignals(False)
            apply_value(v)

        slider.valueChanged.connect(on_slider)
        spin.valueChanged.connect(on_spin)

        # Initial preview at the remembered strength
        apply_value(initial)

        dlg.adjustSize()
        self._position_dialog_away_from_ann(dlg, ann)

        try:
            result = dlg.exec()
        finally:
            self._drawing = None
            self._preview_qimg = None
            self._preview_rect_image = None
            self.update()

        if result != QDialog.DialogCode.Accepted:
            return False
        if ann.kind == _KIND_MOSAIC:
            self._last_block_size = ann.block_size
        else:
            self._last_blur_radius = ann.blur_radius
        # Bake the effect into the base image via an undoable command —
        # the pixels are now "committed" in memory but the file on disk
        # is untouched until the user explicitly hits Save.
        old_img = self._base
        new_img = bake(self._base, [ann])
        cmd = _BakeDestructiveCommand(self, old_img, new_img, text=ann.kind)
        self._undo_stack.push(cmd)
        return True

    def _update_destructive_preview(self, ann: Annotation) -> None:
        """Bake mosaic/blur on the annotation's region and store it as a
        QImage the paintEvent draws over the base. Called live while the
        strength-dialog slider moves.
        """
        x, y, w, h = ann.normalized_rect()
        # Clamp to image bounds — users can rubber-band past the edge.
        x = max(0, x)
        y = max(0, y)
        w = max(1, min(self._base.width - x, w))
        h = max(1, min(self._base.height - y, h))
        if w <= 0 or h <= 0:
            self._preview_qimg = None
            self._preview_rect_image = None
            self.update()
            return
        region = self._base.crop((x, y, x + w, y + h))
        if ann.kind == _KIND_MOSAIC:
            block = max(2, ann.block_size)
            small = region.resize(
                (max(1, w // block), max(1, h // block)),
                resample=Image.Resampling.BILINEAR,
            )
            out = small.resize((w, h), resample=Image.Resampling.NEAREST)
        elif ann.kind == _KIND_BLUR:
            out = region.filter(
                ImageFilter.GaussianBlur(radius=max(1, ann.blur_radius))
            )
        else:
            return
        self._preview_qimg = pil_to_qimage(out)
        self._preview_rect_image = (x, y, w, h)
        self.update()

    def _position_dialog_away_from_ann(self, dlg: QDialog, ann: Annotation) -> None:
        """Move ``dlg`` so it doesn't overlap the annotation's screen rect.

        Tries right → left → below → above. Falls back to clamping inside
        the available screen area so the dialog is never off-screen.
        """
        x1, y1, x2, y2 = ann.bounding_box()
        tl_local = self._image_to_screen(x1, y1)
        br_local = self._image_to_screen(x2, y2)
        tl_global = self.mapToGlobal(QPoint(int(tl_local.x()), int(tl_local.y())))
        br_global = self.mapToGlobal(QPoint(int(br_local.x()), int(br_local.y())))
        ann_rect = QRect(tl_global, br_global).normalized()

        size = dlg.sizeHint()
        dw = max(size.width(), 280)
        dh = max(size.height(), 120)
        gap = 16

        screen = self.screen()
        avail = screen.availableGeometry() if screen is not None else QRect(0, 0, 4096, 4096)

        candidates = [
            # right
            QPoint(ann_rect.right() + gap, ann_rect.top()),
            # left
            QPoint(ann_rect.left() - dw - gap, ann_rect.top()),
            # below
            QPoint(ann_rect.left(), ann_rect.bottom() + gap),
            # above
            QPoint(ann_rect.left(), ann_rect.top() - dh - gap),
        ]
        chosen = None
        for p in candidates:
            r = QRect(p, QSize(dw, dh))
            if avail.contains(r):
                chosen = p
                break
        if chosen is None:
            # Last resort: clamp the first candidate into the screen.
            p = candidates[0]
            cx = max(avail.left(), min(p.x(), avail.right() - dw))
            cy = max(avail.top(), min(p.y(), avail.bottom() - dh))
            chosen = QPoint(cx, cy)
        dlg.move(chosen)

    @staticmethod
    def _resize_points(
        orig: list[tuple[int, int]],
        handle: str,
        dx: int,
        dy: int,
    ) -> list[tuple[int, int]]:
        """Apply a resize-handle drag to a 2-point bounding annotation.

        For freehand / multi-point annotations we only remap the *endpoints*,
        which is imperfect but keeps the interaction simple. A real scale
        around the bounding box centroid would be nicer — worth a follow-up.
        """
        if len(orig) < 2:
            return orig
        x1, y1 = orig[0]
        x2, y2 = orig[-1]
        mnx, mxx = min(x1, x2), max(x1, x2)
        mny, mxy = min(y1, y2), max(y1, y2)
        if "w" in handle:
            mnx += dx
        if "e" in handle:
            mxx += dx
        if "n" in handle:
            mny += dy
        if "s" in handle:
            mxy += dy
        return [(mnx, mny)] + orig[1:-1] + [(mxx, mxy)]

    # ---------- Inline text editor ----------

    def _begin_text_edit(self, ix: int, iy: int) -> None:
        self._cancel_text_edit()
        self._text_anchor_image = (ix, iy)
        edit = QLineEdit(self)
        edit.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,230); "
            "border: 1px solid #0080ff; padding: 2px; }"
        )
        font = edit.font()
        font.setPointSize(14)
        edit.setFont(font)
        pt = self._image_to_screen(ix, iy)
        edit.setGeometry(int(pt.x()), int(pt.y()), 220, 28)
        edit.returnPressed.connect(self._commit_text_edit)
        edit.editingFinished.connect(self._commit_text_edit)
        edit.show()
        edit.setFocus()
        self._text_edit = edit

    def _commit_text_edit(self) -> None:
        if self._text_edit is None or self._text_anchor_image is None:
            return
        text = self._text_edit.text().strip()
        edit = self._text_edit
        anchor = self._text_anchor_image
        # Clear state first so reentrant editingFinished (fires on
        # deleteLater focus-out) doesn't double-commit
        self._text_edit = None
        self._text_anchor_image = None
        edit.deleteLater()
        if text:
            ix, iy = anchor
            ann = Annotation(
                kind=_KIND_TEXT,
                points=[(ix, iy)],
                color=self._color,
                stroke_width=self._stroke_width,
                text=text,
                font_size=self._font_size,
                font_family=self._font_family,
            )
            cmd = _AddAnnotationCommand(self, ann)
            self._undo_stack.push(cmd)
            self.annotation_changed.emit()

    def _cancel_text_edit(self) -> None:
        if self._text_edit is not None:
            edit = self._text_edit
            self._text_edit = None
            self._text_anchor_image = None
            edit.deleteLater()

    # ---------- Keyboard ----------

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_id is not None:
                sel = self._find(self._selected_id)
                if sel is not None:
                    cmd = _DeleteAnnotationCommand(self, sel)
                    self._undo_stack.push(cmd)
                    self.annotation_changed.emit()
                return
        elif key == Qt.Key.Key_Escape:
            self._selected_id = None
            self._cancel_text_edit()
            self.update()
            return
        elif key == Qt.Key.Key_Left and self._text_edit is None:
            self.navigate_image.emit(-1)
            return
        elif key == Qt.Key.Key_Right and self._text_edit is None:
            self.navigate_image.emit(1)
            return
        super().keyPressEvent(event)


def _point_segment_distance(
    px: float, py: float,
    a: tuple[int, int], b: tuple[int, int],
) -> float:
    """Shortest distance from point ``(px,py)`` to segment ``a-b``.

    Used for line/arrow/freehand hit testing so the user can click near
    a diagonal line without having to hit the (much larger) bounding box.
    """
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _handle_cursor(handle: str) -> Qt.CursorShape:
    return {
        "nw": Qt.CursorShape.SizeFDiagCursor,
        "se": Qt.CursorShape.SizeFDiagCursor,
        "ne": Qt.CursorShape.SizeBDiagCursor,
        "sw": Qt.CursorShape.SizeBDiagCursor,
        "n": Qt.CursorShape.SizeVerCursor,
        "s": Qt.CursorShape.SizeVerCursor,
        "e": Qt.CursorShape.SizeHorCursor,
        "w": Qt.CursorShape.SizeHorCursor,
    }.get(handle, Qt.CursorShape.ArrowCursor)


# ---------------------------------------------------------------------------
# Editor widget — reusable QWidget form of the annotation editor.
#
# The same widget is hosted inside the legacy ``AnnotationDialog`` (for the
# clipboard-capture / "open in modal" flow) and can also be dropped into a
# tab / dock panel / any other QWidget container so the full editor —
# menubar, toolbox, canvas, brushes, Modify actions — lives right next to
# the main viewer instead of a separate top-level window.
# ---------------------------------------------------------------------------

class AnnotationEditorWidget(QWidget):
    """Professional-editor QWidget: menubar + toolbox + canvas + right panel.

    Parameters
    ----------
    base:
        The PIL image the editor opens on.
    source_path:
        Path of ``base`` on disk, or ``""`` for in-memory (clipboard) images.
    on_saved:
        Optional callback fired after a successful save to ``source_path``.
    modify_target:
        Optional ``GPUImageView`` — when provided, the editor's menu bar
        grows a "Modify" menu embedding :class:`ModifyActionsWidget`, so
        Develop / Rotate / Flip / Reset are reachable from the editor too.
    parent:
        Usual Qt parent.
    """

    # Fired when the File → Close menu entry is triggered. Host containers
    # decide what "close" means — the legacy dialog connects it to
    # ``QDialog.accept``; a tab host can tear the tab down instead.
    close_requested = Signal()

    def __init__(
        self,
        base: Image.Image,
        source_path: str = "",
        on_saved: Callable[[str], None] | None = None,
        modify_target: GPUImageView | None = None,
        parent=None,
        default_tool: str = "",
    ):
        super().__init__(parent)
        self._source_path = source_path
        self._default_tool = default_tool
        # Optional callback fired after a successful destructive save —
        # used by ``open_annotation_for_path`` to refresh the main viewer.
        self._on_saved = on_saved
        self._modify_target = modify_target

        self._undo_stack = QUndoStack(self)
        self._canvas = AnnotationCanvas(base, self._undo_stack, self)

        # ---------- Root layout ----------
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1) 上方 menu bar — QDialog 沒有原生 menuBar()，但 QVBoxLayout
        # 可透過 setMenuBar 把 QMenuBar 塞到頂端，效果與 QMainWindow 相同。
        self._menu_bar = self._build_menu_bar()
        root.setMenuBar(self._menu_bar)

        # 2) 中段主要內容：左工具箱 / 中央 canvas / 右屬性面板。
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_toolbox = self._build_left_toolbox()
        body.addWidget(self._left_toolbox)

        # Canvas 外面再包一層 QFrame 做暗色背景，模擬 Photoshop / GIMP
        # 在 canvas 四周的 "workspace" 深灰空間感。
        canvas_frame = QFrame(self)
        canvas_frame.setObjectName("annotationCanvasFrame")
        canvas_frame.setFrameShape(QFrame.Shape.NoFrame)
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self._canvas, 1)
        body.addWidget(canvas_frame, 1)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel)

        root.addLayout(body, 1)

        # 3) 底部狀態列 — 顯示當前工具 / 座標 / 影像尺寸。
        self._status_bar = self._build_status_bar()
        root.addWidget(self._status_bar)

        # ---------- Style ----------
        # 不強制黑底（會跟使用者整體 theme 打架），只對幾個關鍵區塊加背景色
        # 與邊框，讓它看起來有 "多面板編輯器" 的分區感。
        self.setStyleSheet(
            """
            QFrame#annotationCanvasFrame {
                background-color: #1e1e1e;
            }
            QFrame#annotationLeftToolbox,
            QFrame#annotationRightPanel {
                background-color: #2d2d30;
                color: #e0e0e0;
                border-right: 1px solid #3f3f42;
            }
            QFrame#annotationRightPanel {
                border-right: none;
                border-left: 1px solid #3f3f42;
            }
            QFrame#annotationLeftToolbox QToolButton,
            QFrame#annotationRightPanel QToolButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
            QFrame#annotationLeftToolbox QToolButton:hover,
            QFrame#annotationRightPanel QToolButton:hover {
                background-color: #4a4a4a;
            }
            QFrame#annotationLeftToolbox QToolButton:checked {
                background-color: #0a6cbc;
                border: 1px solid #3e95d6;
            }
            QFrame#annotationRightPanel QLabel {
                color: #e0e0e0;
            }
            QFrame#annotationRightPanel QLabel#panelSection {
                color: #9cdcfe;
                font-weight: bold;
                padding-top: 6px;
            }
            QFrame#annotationRightPanel QSpinBox,
            QFrame#annotationRightPanel QSlider {
                background-color: #3c3c3c;
                color: #e0e0e0;
            }
            """
        )

        # Connect canvas signals to status bar / property panel updates.
        self._canvas.cursor_image_pos.connect(self._on_cursor_moved)
        self._canvas.tool_changed.connect(self._on_canvas_tool_changed)

        self._install_shortcuts()
        self._refresh_status_bar()

        # Apply default tool if requested (e.g. open directly to mosaic/blur)
        if self._default_tool:
            self._canvas.set_tool(self._default_tool)

    # ========================================================================
    # Professional editor layout — menubar / left toolbox / right panel /
    # status bar. Designed to look like Photoshop / GIMP / Krita: narrow
    # vertical tool column on the left, dockable-looking properties on the
    # right, dark workspace around the canvas, status bar with live readouts.
    # ========================================================================

    # Left toolbox button size — compact, single-column stack. Label still
    # visible so every tool announces itself without relying on tooltips.
    _TOOL_BTN_SIZE = QSize(86, 66)
    _TOOL_BTN_LABEL_POINT = 9
    _LEFT_TOOLBOX_WIDTH = 102
    _RIGHT_PANEL_WIDTH = 248

    # Compact-tool list used by both the toolbox and the keyboard shortcuts.
    # Definition order is the visual stacking order in the left column.
    def _tool_definitions(self) -> list[tuple[str, str, str]]:
        lang = language_wrapper.language_word_dict
        return [
            ("select",   "⬚", lang.get("annotation_tool_select", "Select")),
            ("rect",     "▢", lang.get("annotation_tool_rect", "Rectangle")),
            ("ellipse",  "◯", lang.get("annotation_tool_ellipse", "Ellipse")),
            ("line",     "╱", lang.get("annotation_tool_line", "Line")),
            ("arrow",    "→", lang.get("annotation_tool_arrow", "Arrow")),
            ("freehand", "✎", lang.get("annotation_tool_freehand", "Freehand")),
            ("text",     "T", lang.get("annotation_tool_text", "Text")),
            ("mosaic",   "▦", lang.get("annotation_tool_mosaic", "Mosaic")),
            ("blur",     "◌", lang.get("annotation_tool_blur", "Blur")),
        ]

    def _make_compact_tool_button(self, glyph: str, label: str) -> QToolButton:
        """Small QToolButton with glyph above label — suited for the left
        vertical toolbox. Labels stay visible (per earlier user feedback)
        but the footprint is much tighter than the old 120×96 toolbar.
        """
        btn = QToolButton(self)
        btn.setText(f"{glyph}\n{label}")
        btn.setToolTip(label)
        font = QFont(btn.font())
        font.setPointSize(self._TOOL_BTN_LABEL_POINT)
        btn.setFont(font)
        btn.setFixedSize(self._TOOL_BTN_SIZE)
        return btn

    # ---------- Menu bar ----------

    def _build_menu_bar(self) -> QMenuBar:
        """File / Edit menu bar, Photoshop-style.

        Actions previously living in the bottom button row (Save, Save As,
        Copy, Save Project, Load Project) are moved here; Edit holds
        Undo / Redo / Delete Selection. Every action has a keyboard
        shortcut attached so power users don't need the menu at all.
        """
        lang = language_wrapper.language_word_dict
        mb = QMenuBar(self)

        # ---- File ----
        file_menu = mb.addMenu(lang.get("annotation_menu_file", "File"))

        act_save = QAction(lang.get("annotation_save", "Save"), self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save)
        file_menu.addAction(act_save)

        act_save_as = QAction(lang.get("annotation_save_as", "Save As..."), self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self._save_as)
        file_menu.addAction(act_save_as)

        act_copy = QAction(
            lang.get("annotation_copy_clipboard", "Copy to Clipboard"), self
        )
        act_copy.setShortcut(QKeySequence("Ctrl+C"))
        act_copy.triggered.connect(self._copy_to_clipboard)
        file_menu.addAction(act_copy)

        file_menu.addSeparator()

        act_save_proj = QAction(
            lang.get("annotation_save_project", "Save Project..."), self
        )
        act_save_proj.triggered.connect(self._save_project)
        file_menu.addAction(act_save_proj)

        act_load_proj = QAction(
            lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK), self
        )
        act_load_proj.triggered.connect(self._load_project)
        file_menu.addAction(act_load_proj)

        file_menu.addSeparator()

        act_close = QAction(lang.get("annotation_menu_close", "Close"), self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        # Emit a signal instead of calling ``self.close``: the editor widget
        # may be embedded in a dialog, tab, or dock — each host decides what
        # "close" means (dialog.accept, tab removal, panel hide, ...).
        act_close.triggered.connect(self.close_requested.emit)
        file_menu.addAction(act_close)

        # ---- Edit ----
        edit_menu = mb.addMenu(lang.get("annotation_menu_edit", "Edit"))

        act_undo = self._undo_stack.createUndoAction(
            self, lang.get("annotation_undo", "Undo")
        )
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(act_undo)

        act_redo = self._undo_stack.createRedoAction(
            self, lang.get("annotation_redo", "Redo")
        )
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()

        act_delete = QAction(
            lang.get("annotation_menu_delete_selection", "Delete Selection"),
            self,
        )
        act_delete.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        act_delete.triggered.connect(self._delete_selected)
        edit_menu.addAction(act_delete)

        # ---- Modify ----
        # Only built when a ``modify_target`` (GPUImageView) was supplied,
        # because Develop / Rotate / Flip / Reset operate on the main
        # viewer's current image, not on the in-editor PIL copy. Tests
        # and the clipboard-capture flow don't pass a target, so the menu
        # is simply absent there.
        if self._modify_target is not None:
            from Imervue.gui.modify_actions_widget import ModifyActionsWidget

            modify_menu = mb.addMenu(lang.get("modify_menu_title", "Modify"))
            modify_widget_action = QWidgetAction(modify_menu)
            modify_widget = ModifyActionsWidget(
                main_gui=self._modify_target,
                parent=modify_menu,
                on_triggered=modify_menu.close,
            )
            modify_widget_action.setDefaultWidget(modify_widget)
            modify_menu.addAction(modify_widget_action)

        return mb

    # ---------- Left toolbox ----------

    def _build_left_toolbox(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("annotationLeftToolbox")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setFixedWidth(self._LEFT_TOOLBOX_WIDTH)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(4)

        lang = language_wrapper.language_word_dict
        header = QLabel(lang.get("annotation_tools_section", "Tools"), frame)
        header.setObjectName(_QSS_PANEL_SECTION)
        header.setStyleSheet(
            "color: #9cdcfe; font-weight: bold; padding-bottom: 4px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(header)

        self._tool_buttons: dict[str, QToolButton] = {}
        for tool, glyph, label in self._tool_definitions():
            btn = self._make_compact_tool_button(glyph, label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, t=tool: self._on_tool_selected(t))
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._tool_buttons[tool] = btn
        self._tool_buttons["select"].setChecked(True)

        lay.addStretch(1)
        return frame

    # ---------- Right properties panel ----------

    def _build_right_panel(self) -> QFrame:
        lang = language_wrapper.language_word_dict
        frame = QFrame(self)
        frame.setObjectName("annotationRightPanel")
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setFixedWidth(self._RIGHT_PANEL_WIDTH)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)

        title = QLabel(lang.get("annotation_properties", "Properties"), frame)
        title_font = QFont(title.font())
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        lay.addWidget(title)

        # Current tool readout — big and obvious, mirrors Photoshop's
        # tool-options strip where the active tool name is always visible.
        self._current_tool_label = QLabel("", frame)
        ct_font = QFont(self._current_tool_label.font())
        ct_font.setPointSize(10)
        self._current_tool_label.setFont(ct_font)
        self._current_tool_label.setStyleSheet("color: #cccccc;")
        lay.addWidget(self._current_tool_label)

        lay.addSpacing(6)

        # ---- Color section ----
        color_section = QLabel(
            lang.get("annotation_color", "Color"), frame
        )
        color_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(color_section)

        self._color = (255, 0, 0, 255)
        self._color_btn = QToolButton(frame)
        self._color_btn.setText(lang.get("annotation_color", "Color"))
        self._color_btn.setFixedHeight(44)
        self._color_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._color_btn.setAutoRaise(False)
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_button_style()
        lay.addWidget(self._color_btn)

        lay.addSpacing(4)

        # ---- Stroke width section ----
        sw_section = QLabel(
            lang.get("annotation_stroke_width_label", "Stroke Width"), frame
        )
        sw_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(sw_section)

        sw_row = QHBoxLayout()
        sw_row.setContentsMargins(0, 0, 0, 0)
        sw_row.setSpacing(6)

        self._width_slider = QSlider(Qt.Orientation.Horizontal, frame)
        self._width_slider.setRange(1, 40)
        self._width_slider.setValue(3)
        sw_row.addWidget(self._width_slider, 1)

        self._width_spin = QSpinBox(frame)
        self._width_spin.setRange(1, 40)
        self._width_spin.setValue(3)
        self._width_spin.setFixedWidth(70)
        sw_row.addWidget(self._width_spin)

        lay.addLayout(sw_row)

        # Two-way sync between slider and spin, and propagate to canvas.
        def on_slider(v: int) -> None:
            self._width_spin.blockSignals(True)
            self._width_spin.setValue(v)
            self._width_spin.blockSignals(False)
            self._canvas.set_stroke_width(v)
            self._refresh_status_bar()

        def on_spin(v: int) -> None:
            self._width_slider.blockSignals(True)
            self._width_slider.setValue(v)
            self._width_slider.blockSignals(False)
            self._canvas.set_stroke_width(v)
            self._refresh_status_bar()

        self._width_slider.valueChanged.connect(on_slider)
        self._width_spin.valueChanged.connect(on_spin)

        lay.addSpacing(8)

        # ---- History quick actions (Undo / Redo) ----
        hist_section = QLabel(
            lang.get("annotation_history_section", "History"), frame
        )
        hist_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(hist_section)

        hist_row = QHBoxLayout()
        hist_row.setContentsMargins(0, 0, 0, 0)
        hist_row.setSpacing(6)

        undo_btn = QToolButton(frame)
        undo_btn.setText("↶ " + lang.get("annotation_undo", "Undo"))
        undo_btn.setFixedHeight(36)
        undo_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        undo_btn.clicked.connect(self._undo_stack.undo)
        hist_row.addWidget(undo_btn)

        redo_btn = QToolButton(frame)
        redo_btn.setText("↷ " + lang.get("annotation_redo", "Redo"))
        redo_btn.setFixedHeight(36)
        redo_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        redo_btn.clicked.connect(self._undo_stack.redo)
        hist_row.addWidget(redo_btn)

        lay.addLayout(hist_row)

        lay.addSpacing(8)

        # ---- Brush section (freehand only) ----
        brush_section = QLabel(
            lang.get("annotation_brush_section", "Brush"), frame
        )
        brush_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(brush_section)

        brush_grid = QGridLayout()
        brush_grid.setContentsMargins(0, 0, 0, 0)
        brush_grid.setSpacing(4)

        self._brush_buttons: dict[str, QToolButton] = {}
        self._brush_button_group = QButtonGroup(frame)
        self._brush_button_group.setExclusive(True)
        brush_defs: list[tuple[str, str, str]] = [
            ("pen",         "✒",  lang.get("annotation_brush_pen",         "Pen")),
            ("marker",      "🖊", lang.get("annotation_brush_marker",      "Marker")),
            ("pencil",      "✏",  lang.get("annotation_brush_pencil",      "Pencil")),
            ("highlighter", "🖍", lang.get("annotation_brush_highlighter", "Highlighter")),
            ("spray",       "💨", lang.get("annotation_brush_spray",       "Spray")),
        ]
        for idx, (key, glyph, label) in enumerate(brush_defs):
            btn = QToolButton(frame)
            btn.setText(f"{glyph} {label}")
            btn.setCheckable(True)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _=False, k=key: self._on_brush_selected(k))
            row, col = divmod(idx, 2)
            brush_grid.addWidget(btn, row, col)
            self._brush_buttons[key] = btn
            self._brush_button_group.addButton(btn)
        self._brush_buttons["pen"].setChecked(True)
        lay.addLayout(brush_grid)

        lay.addSpacing(4)

        # Opacity slider + spin
        op_section = QLabel(
            lang.get("annotation_opacity", "Opacity"), frame
        )
        op_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(op_section)

        op_row = QHBoxLayout()
        op_row.setContentsMargins(0, 0, 0, 0)
        op_row.setSpacing(6)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, frame)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        op_row.addWidget(self._opacity_slider, 1)
        self._opacity_spin = QSpinBox(frame)
        self._opacity_spin.setRange(0, 100)
        self._opacity_spin.setValue(100)
        self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setFixedWidth(70)
        op_row.addWidget(self._opacity_spin)
        lay.addLayout(op_row)

        def on_opacity_slider(v: int) -> None:
            self._opacity_spin.blockSignals(True)
            self._opacity_spin.setValue(v)
            self._opacity_spin.blockSignals(False)
            self._canvas.set_brush_opacity(v)

        def on_opacity_spin(v: int) -> None:
            self._opacity_slider.blockSignals(True)
            self._opacity_slider.setValue(v)
            self._opacity_slider.blockSignals(False)
            self._canvas.set_brush_opacity(v)

        self._opacity_slider.valueChanged.connect(on_opacity_slider)
        self._opacity_spin.valueChanged.connect(on_opacity_spin)

        lay.addSpacing(4)

        # Spacing slider + spin (spray only, but always visible for clarity)
        sp_section = QLabel(
            lang.get("annotation_spacing", "Spacing"), frame
        )
        sp_section.setObjectName(_QSS_PANEL_SECTION)
        lay.addWidget(sp_section)

        sp_row = QHBoxLayout()
        sp_row.setContentsMargins(0, 0, 0, 0)
        sp_row.setSpacing(6)
        self._spacing_slider = QSlider(Qt.Orientation.Horizontal, frame)
        self._spacing_slider.setRange(1, 40)
        self._spacing_slider.setValue(8)
        sp_row.addWidget(self._spacing_slider, 1)
        self._spacing_spin = QSpinBox(frame)
        self._spacing_spin.setRange(1, 40)
        self._spacing_spin.setValue(8)
        self._spacing_spin.setFixedWidth(70)
        sp_row.addWidget(self._spacing_spin)
        lay.addLayout(sp_row)

        def on_spacing_slider(v: int) -> None:
            self._spacing_spin.blockSignals(True)
            self._spacing_spin.setValue(v)
            self._spacing_spin.blockSignals(False)
            self._canvas.set_brush_spacing(v)

        def on_spacing_spin(v: int) -> None:
            self._spacing_slider.blockSignals(True)
            self._spacing_slider.setValue(v)
            self._spacing_slider.blockSignals(False)
            self._canvas.set_brush_spacing(v)

        self._spacing_slider.valueChanged.connect(on_spacing_slider)
        self._spacing_spin.valueChanged.connect(on_spacing_spin)

        lay.addStretch(1)
        return frame

    def _on_brush_selected(self, brush: str) -> None:
        if brush not in self._brush_buttons:
            return
        for key, btn in self._brush_buttons.items():
            btn.setChecked(key == brush)
        self._canvas.set_brush_type(brush)

    # ---------- Status bar ----------

    def _build_status_bar(self) -> QStatusBar:
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        bar.setStyleSheet(
            "QStatusBar { background-color: #007acc; color: white; }"
            "QStatusBar QLabel { color: white; padding: 0 8px; }"
        )

        self._status_tool_label = QLabel("", bar)
        self._status_pos_label = QLabel("", bar)
        self._status_size_label = QLabel("", bar)

        bar.addWidget(self._status_tool_label, 1)
        bar.addPermanentWidget(self._status_pos_label)
        bar.addPermanentWidget(self._status_size_label)
        return bar

    # ---------- Status / panel refresh helpers ----------

    def _tool_display_label(self, tool: str) -> str:
        for key, _glyph, label in self._tool_definitions():
            if key == tool:
                return label
        return tool

    def _refresh_status_bar(self) -> None:
        lang = language_wrapper.language_word_dict
        tool_label = self._tool_display_label(self._canvas.current_tool())
        self._status_tool_label.setText(
            f"{lang.get('annotation_status_tool', 'Tool')}: {tool_label}"
        )
        base = self._canvas.get_base_pil()
        self._status_size_label.setText(
            f"{lang.get('annotation_status_size', 'Size')}: "
            f"{base.width} × {base.height}"
        )
        if self._current_tool_label is not None:
            self._current_tool_label.setText(
                f"{lang.get('annotation_current_tool', 'Current Tool')}: "
                f"{tool_label}"
            )

    def _on_cursor_moved(self, ix: int, iy: int) -> None:
        lang = language_wrapper.language_word_dict
        self._status_pos_label.setText(
            f"{lang.get('annotation_status_pos', 'Pos')}: "
            f"{ix}, {iy}"
        )

    def _on_canvas_tool_changed(self, tool: str) -> None:
        # Keep the toolbox highlight in sync with set_tool calls that
        # originate from keyboard shortcuts rather than button clicks.
        for name, btn in self._tool_buttons.items():
            btn.setChecked(name == tool)
        self._refresh_status_bar()

    def _delete_selected(self) -> None:
        """Edit → Delete Selection — forwards to the canvas's delete path."""
        sel_id = self._canvas._selected_id
        if sel_id is None:
            return
        sel = self._canvas._find(sel_id)
        if sel is None:
            return
        cmd = _DeleteAnnotationCommand(self._canvas, sel)
        self._undo_stack.push(cmd)
        self._canvas.annotation_changed.emit()

    def _install_shortcuts(self) -> None:
        """Shortcuts that aren't already attached to a menu QAction.

        Save / Save As / Copy / Undo / Redo / Delete live on actions in
        the menu bar, so their QKeySequences fire automatically when the
        dialog has focus. This hook is reserved for anything that isn't
        menu-reachable — currently empty but kept so subclasses / future
        features have an obvious extension point.
        """
        pass

    # ---------- Toolbar handlers ----------

    def _on_tool_selected(self, tool: str) -> None:
        for name, btn in self._tool_buttons.items():
            btn.setChecked(name == tool)
        self._canvas.set_tool(tool)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(
            QColor(*self._color),
            self,
            language_wrapper.language_word_dict.get("annotation_color", "Color"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if c.isValid():
            self._color = (c.red(), c.green(), c.blue(), c.alpha())
            self._update_color_button_style()
            self._canvas.set_color(self._color)

    def _update_color_button_style(self) -> None:
        r, g, b, a = self._color
        text_color = "black" if (r + g + b) > 384 else "white"
        self._color_btn.setStyleSheet(
            f"QToolButton {{ background-color: rgba({r},{g},{b},{a}); "
            f"color: {text_color}; border: 1px solid #888; padding: 4px 10px; }}"
        )

    # ---------- Save / export ----------

    def _baked_image(self) -> Image.Image:
        return bake(self._canvas.get_base_pil(), self._canvas.get_annotations())

    def _save(self) -> None:
        if not self._source_path:
            self._save_as()
            return
        self._write(self._source_path)

    def _save_as(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("annotation_save_as", "Save As..."),
            start_dir,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp);;TIFF (*.tiff)",
        )
        if path:
            self._write(path)

    def _write(self, path: str) -> None:
        """Atomically save the baked image to ``path``.

        Writes to a sibling .tmp file then ``os.replace`` to avoid leaving
        a half-written file if the process is interrupted mid-save. This
        also matters because the source path may be open in the main
        viewer — replacing the file in one atomic step is friendlier than
        truncating the original.
        """
        img = self._baked_image()
        ext = Path(path).suffix.lower()
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        # Pass ``format=`` explicitly because the .tmp extension would
        # otherwise stop PIL from inferring the encoder.
        fmt_by_ext = {
            ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
            ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
            ".webp": "WEBP",
        }
        fmt = fmt_by_ext.get(ext, "PNG")
        try:
            if ext in (".jpg", ".jpeg"):
                img.convert("RGB").save(tmp, format="JPEG", quality=95)
            else:
                img.save(tmp, format=fmt)
            os.replace(tmp, target)
            self._notify_success(
                language_wrapper.language_word_dict.get("annotation_saved", "Saved")
            )
            if self._on_saved is not None and str(target) == self._source_path:
                try:
                    self._on_saved(str(target))
                except Exception:
                    logger.exception("on_saved callback raised")
        except Exception as exc:
            logger.exception("annotation save failed: %s", path)
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            QMessageBox.critical(self, "Error", str(exc))

    def _copy_to_clipboard(self) -> None:
        img = self._baked_image()
        qimg = pil_to_qimage(img)
        QApplication.clipboard().setImage(qimg)
        self._notify_success(
            language_wrapper.language_word_dict.get(
                "annotation_copy_success", "Copied to clipboard"
            )
        )

    def _save_project(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        suggested = ""
        if self._source_path:
            suggested = str(
                Path(start_dir) / (Path(self._source_path).stem + ".imervue_annot.json")
            )
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("annotation_save_project", "Save Project..."),
            suggested or start_dir,
            "Imervue Annotation Project (*.imervue_annot.json *.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".imervue_annot.json"
        base = self._canvas.get_base_pil()
        project = AnnotationProject(
            source_path=self._source_path,
            source_size=(base.width, base.height),
            annotations=self._canvas.get_annotations(),
        )
        try:
            project.save(path)
            self._notify_success(
                lang.get("annotation_saved", "Saved")
            )
        except Exception as exc:
            logger.exception("project save failed: %s", path)
            QMessageBox.critical(self, "Error", str(exc))

    def _load_project(self) -> None:
        lang = language_wrapper.language_word_dict
        start_dir = str(Path(self._source_path).parent) if self._source_path else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK),
            start_dir,
            "Imervue Annotation Project (*.json)",
        )
        if not path:
            return
        try:
            project = AnnotationProject.load(path)
        except Exception as exc:
            logger.exception("project load failed: %s", path)
            QMessageBox.critical(self, "Error", str(exc))
            return

        base = self._canvas.get_base_pil()
        if project.source_size not in {(0, 0), (base.width, base.height)}:
            warning = lang.get(
                "annotation_project_size_mismatch",
                "Project was saved against a {pw}x{ph} image; current image "
                "is {cw}x{ch}. Annotation positions may be off.",
            ).format(
                pw=project.source_size[0], ph=project.source_size[1],
                cw=base.width, ch=base.height,
            )
            QMessageBox.warning(
                self,
                lang.get("annotation_load_project", _LOAD_PROJECT_FALLBACK),
                warning,
            )
        self._canvas.set_annotations(project.annotations)

    def _notify_success(self, message: str) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "toast"):
            parent.toast.success(message)
        else:
            logger.info(message)


# ---------------------------------------------------------------------------
# Legacy dialog wrapper
# ---------------------------------------------------------------------------

class AnnotationDialog(QDialog):
    """Thin ``QDialog`` wrapper hosting an :class:`AnnotationEditorWidget`.

    Kept so callers that want the editor as a modal window (clipboard
    capture, right-click menu) don't have to manage a top-level widget
    themselves. Any attribute access that isn't defined on the dialog
    falls through to the embedded editor — tests rely on poking
    ``dlg._canvas`` / ``dlg._baked_image()`` / ``dlg._write()`` / etc.
    directly, and that needs to keep working after the refactor.
    """

    def __init__(
        self,
        base: Image.Image,
        source_path: str = "",
        parent=None,
        on_saved: Callable[[str], None] | None = None,
        modify_target: GPUImageView | None = None,
        default_tool: str = "",
    ):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("annotation_title", "Annotate"))

        # 專業繪圖軟體風格的預設尺寸 — 超過螢幕時縮到 95%。
        default_w, default_h = 1280, 960
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is None and parent is not None:
            screen = parent.screen() if hasattr(parent, "screen") else None
        if screen is not None:
            avail = screen.availableGeometry()
            default_w = min(default_w, int(avail.width() * 0.95))
            default_h = min(default_h, int(avail.height() * 0.95))
        self.resize(default_w, default_h)

        self._editor = AnnotationEditorWidget(
            base,
            source_path=source_path,
            on_saved=on_saved,
            modify_target=modify_target,
            parent=self,
            default_tool=default_tool,
        )
        # File → Close in the editor closes this hosting dialog.
        self._editor.close_requested.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._editor)

    def __getattr__(self, name: str):
        # ``__getattr__`` only fires when normal lookup fails, so dialog
        # attributes still take precedence. Everything else — canvas,
        # tool buttons, color state, save helpers — lives on the editor
        # widget and is forwarded transparently.
        if name.startswith("__"):
            raise AttributeError(name)
        editor = self.__dict__.get("_editor")
        if editor is None:
            raise AttributeError(name)
        return getattr(editor, name)


# ---------------------------------------------------------------------------
# Entry points (called from right-click menu / main window)
# ---------------------------------------------------------------------------

def open_annotation_for_path(
    main_gui: GPUImageView, path: str, default_tool: str = "",
) -> None:
    """Load ``path`` with PIL and open the annotation dialog on it.

    On a successful destructive save, refresh the main viewer so the
    annotated pixels appear immediately instead of the user having to
    click away and back.
    """
    try:
        img = Image.open(path)
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert(_MODE_RGBA)
        else:
            img.load()  # force decode now so errors surface before the dialog
    except Exception as exc:
        logger.exception("annotation load failed: %s", path)
        if hasattr(main_gui.main_window, "toast"):
            main_gui.main_window.toast.error(f"Load failed: {exc}")
        return

    def _reload(saved_path: str) -> None:
        # Lazy import to avoid a top-level dependency on the viewer module
        # for the offline-testable parts of this file.
        from Imervue.gpu_image_view.images.image_loader import open_path
        with contextlib.suppress(Exception):
            main_gui._clear_deep_zoom()
        try:
            open_path(main_gui=main_gui, path=saved_path)
        except Exception:
            logger.exception("viewer reload after annotation save failed")

    dlg = AnnotationDialog(
        img,
        source_path=path,
        parent=main_gui.main_window,
        on_saved=_reload,
        modify_target=main_gui,
        default_tool=default_tool,
    )
    dlg.exec()


def open_annotation_for_clipboard_image(
    parent_window, img: Image.Image
) -> None:
    """Open the annotation dialog on a clipboard PIL image (no source path)."""
    dlg = AnnotationDialog(img, source_path="", parent=parent_window)
    dlg.exec()
