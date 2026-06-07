"""Annotation canvas widget and undo commands.

The interactive markup canvas (freehand, shapes, text, mosaic/blur, crop,
selection), its QUndoCommand classes, and the PIL<->QImage helpers. Extracted
from ``annotation_dialog`` to keep that module within the file-length budget;
re-exported there for backwards compatibility.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QImage, QMouseEvent,
    QPainter, QPainterPath, QPen, QPolygonF, QUndoCommand, QUndoStack,
)
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox,
    QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from Imervue.gui.annotation_models import (
    ALL_BRUSHES, Annotation, AnnotationKind, bake,
)
from Imervue.multi_language.language_wrapper import language_wrapper


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


def _apply_alpha(rgba: tuple[int, int, int, int], multiplier: float) -> QColor:
    r, g, b, a = rgba
    return QColor(r, g, b, int(a * multiplier))


def _draw_simple_path(painter: QPainter, points: list[tuple[float, float]]) -> None:
    path = QPainterPath()
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    painter.drawPath(path)


class AnnotationCanvas(QWidget):
    """Interactive canvas that renders a PIL base image + annotation overlay.

    All Annotation.points are stored in image coordinates; the canvas maps
    between image coords and widget coords via ``_display_rect``.
    """

    annotation_changed = Signal()
    # Emitted whenever the mouse moves over the canvas, in image coordinates.
    # Used by the dialog's status bar to show a live cursor readout just like
    # a professional editor does (Photoshop / external image editors /  all have this).
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
            self._paint_image_and_annotations(painter, rect)
        if self._selected_id is not None:
            sel = self._find(self._selected_id)
            if sel is not None:
                self._draw_selection(painter, sel)
        if (self._tool == _KIND_CROP and self._crop_rect is not None
                and rect.width() > 0):
            self._paint_crop_overlay(painter, rect)
        painter.end()

    def _paint_image_and_annotations(self, painter: QPainter, rect: QRectF) -> None:
        painter.drawImage(rect, self._base_qimg)
        painter.save()
        painter.translate(rect.x(), rect.y())
        painter.scale(
            rect.width() / self._base.width,
            rect.height() / self._base.height,
        )
        if (self._preview_qimg is not None
                and self._preview_rect_image is not None):
            px, py, pw, ph = self._preview_rect_image
            painter.drawImage(QRectF(px, py, pw, ph), self._preview_qimg)
        for ann in self._annotations:
            self._draw_annotation_qt(painter, ann)
        if self._drawing is not None:
            self._draw_annotation_qt(painter, self._drawing)
        painter.restore()

    def _paint_crop_overlay(self, painter: QPainter, rect: QRectF) -> None:
        cx, cy, cw, ch = self._crop_rect
        tl = self._image_to_screen(cx, cy)
        br = self._image_to_screen(cx + cw, cy + ch)
        crop_screen = QRectF(tl, br).normalized()
        self._paint_crop_dimming(painter, rect, crop_screen)
        self._paint_crop_border(painter, crop_screen)
        self._paint_crop_thirds(painter, crop_screen)
        self._paint_crop_handles(painter, crop_screen)
        self._paint_crop_size_label(painter, crop_screen, cw, ch)

    @staticmethod
    def _paint_crop_dimming(painter: QPainter, rect: QRectF, crop_screen: QRectF) -> None:
        dim = QColor(0, 0, 0, 140)
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(),
                                crop_screen.top() - rect.top()), dim)
        painter.fillRect(QRectF(rect.left(), crop_screen.bottom(),
                                rect.width(), rect.bottom() - crop_screen.bottom()), dim)
        painter.fillRect(QRectF(rect.left(), crop_screen.top(),
                                crop_screen.left() - rect.left(),
                                crop_screen.height()), dim)
        painter.fillRect(QRectF(crop_screen.right(), crop_screen.top(),
                                rect.right() - crop_screen.right(),
                                crop_screen.height()), dim)

    @staticmethod
    def _paint_crop_border(painter: QPainter, crop_screen: QRectF) -> None:
        crop_pen = QPen(QColor(255, 255, 255))
        crop_pen.setWidthF(1.5)
        crop_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(crop_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(crop_screen)

    @staticmethod
    def _paint_crop_thirds(painter: QPainter, crop_screen: QRectF) -> None:
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

    def _paint_crop_handles(self, painter: QPainter, crop_screen: QRectF) -> None:
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        h = _HANDLE_SIZE
        for hx, hy in self._handle_positions(crop_screen):
            painter.drawRect(QRectF(hx - h / 2, hy - h / 2, h, h))

    @staticmethod
    def _paint_crop_size_label(painter: QPainter, crop_screen: QRectF,
                               cw: int, ch: int) -> None:
        painter.setPen(QPen(QColor(255, 255, 255)))
        label_font = QFont()
        label_font.setPixelSize(12)
        painter.setFont(label_font)
        painter.drawText(
            QPointF(crop_screen.left() + 4, crop_screen.top() - 4),
            f"{cw} x {ch}")

    def _draw_annotation_qt(self, painter: QPainter, ann: Annotation) -> None:
        color = QColor(*ann.color)
        self._prepare_annotation_pen(painter, ann, color)
        dispatch = {
            "rect": self._draw_rect_qt,
            "ellipse": self._draw_ellipse_qt,
            _KIND_LINE: self._draw_line_qt,
            _KIND_ARROW: self._draw_arrow_qt,
            _KIND_FREEHAND: self._draw_freehand_if_valid,
            _KIND_TEXT: self._draw_text_qt,
        }
        handler = dispatch.get(ann.kind)
        if handler is not None:
            handler(painter, ann)
        elif ann.kind in (_KIND_MOSAIC, _KIND_BLUR):
            self._draw_pixel_effect_preview(painter, ann, color)

    @staticmethod
    def _prepare_annotation_pen(painter: QPainter, ann: Annotation, color: QColor) -> None:
        pen = QPen(color)
        pen.setWidthF(ann.stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(color) if ann.filled else Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_rect_qt(painter: QPainter, ann: Annotation) -> None:
        x1, y1, x2, y2 = ann.bounding_box()
        painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

    @staticmethod
    def _draw_ellipse_qt(painter: QPainter, ann: Annotation) -> None:
        x1, y1, x2, y2 = ann.bounding_box()
        painter.drawEllipse(QRectF(x1, y1, x2 - x1, y2 - y1))

    @staticmethod
    def _draw_line_qt(painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) >= 2:
            painter.drawLine(QPointF(*ann.points[0]),
                             QPointF(*ann.points[-1]))

    def _draw_freehand_if_valid(self, painter: QPainter, ann: Annotation) -> None:
        if len(ann.points) >= 2:
            self._draw_freehand_qt(painter, ann)

    @staticmethod
    def _draw_text_qt(painter: QPainter, ann: Annotation) -> None:
        if not (ann.text and ann.points):
            return
        font = QFont(ann.font_family) if ann.font_family else QFont()
        font.setPixelSize(max(6, ann.font_size))
        painter.setFont(font)
        painter.setPen(QPen(QColor(*ann.color)))
        painter.drawText(QPointF(*ann.points[0]), ann.text)

    @staticmethod
    def _draw_pixel_effect_preview(painter: QPainter, ann: Annotation, color: QColor) -> None:
        preview_pen = QPen(color)
        preview_pen.setWidthF(2)
        preview_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(preview_pen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
        x1, y1, x2, y2 = ann.bounding_box()
        region = QRectF(x1, y1, x2 - x1, y2 - y1)
        painter.drawRect(region)
        label_font = QFont()
        label_font.setPixelSize(max(12, int(min(region.width(), region.height()) / 8)))
        painter.setFont(label_font)
        painter.drawText(region, Qt.AlignmentFlag.AlignCenter, ann.kind)

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
        if self._dispatch_dedicated_brush(painter, ann, brush, opacity):
            return

        alpha_scale, width_factor = self._BRUSH_PRESETS.get(
            brush, self._BRUSH_PRESETS["pen"]
        )
        width = max(1, int(ann.stroke_width * width_factor))
        color = _apply_alpha(ann.color, alpha_scale * opacity / 100)
        self._apply_simple_brush_pen(painter, color, width)

        if brush == "watercolor":
            self._draw_watercolor_qt(painter, ann, width)
        elif brush == "crayon":
            self._draw_crayon_qt(painter, ann, color, width)
        else:
            _draw_simple_path(painter, ann.points)

    def _dispatch_dedicated_brush(
        self, painter: QPainter, ann: Annotation, brush: str, opacity: int
    ) -> bool:
        if brush == "spray":
            self._draw_freehand_spray_qt(painter, ann, opacity)
            return True
        if brush == "calligraphy":
            self._draw_freehand_calligraphy_qt(painter, ann, opacity)
            return True
        if brush == "charcoal":
            self._draw_freehand_charcoal_qt(painter, ann, opacity)
            return True
        return False

    @staticmethod
    def _apply_simple_brush_pen(painter: QPainter, color: QColor, width: int) -> None:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_watercolor_qt(painter: QPainter, ann: Annotation, width: int) -> None:
        import random as _random
        rng = _random.Random(hash(ann.id) & 0xFFFFFFFF)
        jitter = width * 0.15
        for _ in range(3):
            path = QPainterPath()
            pts = ann.points
            path.moveTo(pts[0][0] + rng.gauss(0, jitter),
                        pts[0][1] + rng.gauss(0, jitter))
            for px, py in pts[1:]:
                path.lineTo(px + rng.gauss(0, jitter),
                            py + rng.gauss(0, jitter))
            painter.drawPath(path)

    @staticmethod
    def _draw_crayon_qt(painter: QPainter, ann: Annotation,
                        color: QColor, width: int) -> None:
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
            if self._annotation_hits_point(a, ix, iy):
                return a
        return None

    def _annotation_hits_point(self, a: Annotation, ix: int, iy: int) -> bool:
        """Hit-test ``a`` at image-space (ix, iy) using a kind-aware metric."""
        tol = max(5, a.stroke_width + 2)
        if a.kind in ("line", "arrow"):
            return self._line_annotation_hits(a, ix, iy, tol)
        if a.kind == _KIND_FREEHAND:
            return self._freehand_annotation_hits(a, ix, iy, tol)
        return self._bbox_annotation_hits(a, ix, iy, tol)

    @staticmethod
    def _line_annotation_hits(a: Annotation, ix: int, iy: int, tol: float) -> bool:
        if len(a.points) < 2:
            return False
        return _point_segment_distance(ix, iy, a.points[0], a.points[-1]) <= tol

    @staticmethod
    def _freehand_annotation_hits(a: Annotation, ix: int, iy: int, tol: float) -> bool:
        if len(a.points) < 2:
            return False
        return any(
            _point_segment_distance(ix, iy, p, q) <= tol
            for p, q in zip(a.points, a.points[1:], strict=False)
        )

    def _bbox_annotation_hits(
        self, a: Annotation, ix: int, iy: int, tol: float,
    ) -> bool:
        if a.kind == _KIND_TEXT:
            x1, y1, x2, y2 = self._text_bounding_box(a)
        else:
            x1, y1, x2, y2 = a.bounding_box()
        return x1 - tol <= ix <= x2 + tol and y1 - tol <= iy <= y2 + tol

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

        if self._tool == _KIND_CROP:
            self._press_crop(pt, ix, iy)
            return
        if self._tool == _KIND_SELECT:
            self._press_select(pt, ix, iy)
            return
        if self._tool == _KIND_TEXT:
            self._begin_text_edit(ix, iy)
            return
        self._begin_shape(ix, iy)

    def _press_crop(self, pt, ix: int, iy: int) -> None:
        handle = self._crop_hit_handle(pt) if self._crop_rect else None
        if handle is not None:
            self._crop_dragging = True
            self._crop_drag_start = (ix, iy)
            self._crop_drag_handle = handle
            self._crop_drag_orig = self._crop_rect
            return
        self._crop_rect = (ix, iy, 0, 0)
        self._crop_dragging = True
        self._crop_drag_start = (ix, iy)
        self._crop_drag_handle = None
        self._crop_drag_orig = None

    def _press_select(self, pt, ix: int, iy: int) -> None:
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

    def _begin_shape(self, ix: int, iy: int) -> None:
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
        """
        cfg = self._destructive_prompt_config(ann)
        if cfg is None:
            return True
        title, label_text, minv, maxv = cfg
        initial = (self._last_block_size if ann.kind == _KIND_MOSAIC
                   else self._last_blur_radius)
        self._drawing = ann  # keep dashed-outline preview visible during dialog
        dlg, slider, spin = self._build_strength_dialog(title, label_text, minv, maxv, initial)
        self._wire_strength_signals(dlg, slider, spin, ann, initial)
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
        self._commit_destructive(ann)
        return True

    @staticmethod
    def _destructive_prompt_config(
        ann: Annotation,
    ) -> tuple[str, str, int, int] | None:
        lang = language_wrapper.language_word_dict
        if ann.kind == _KIND_MOSAIC:
            return (
                lang.get("annotation_mosaic_prompt_title", "Mosaic strength"),
                lang.get("annotation_mosaic_prompt_label", "Block size (pixels):"),
                2, 200,
            )
        if ann.kind == _KIND_BLUR:
            return (
                lang.get("annotation_blur_prompt_title", "Blur strength"),
                lang.get("annotation_blur_prompt_label", "Gaussian radius (pixels):"),
                1, 200,
            )
        return None

    def _build_strength_dialog(
        self, title: str, label_text: str, minv: int, maxv: int, initial: int
    ) -> tuple[QDialog, QSlider, QSpinBox]:
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
        return dlg, slider, spin

    def _wire_strength_signals(
        self, dlg: QDialog, slider: QSlider, spin: QSpinBox,
        ann: Annotation, initial: int,
    ) -> None:
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
        apply_value(initial)

    def _commit_destructive(self, ann: Annotation) -> None:
        if ann.kind == _KIND_MOSAIC:
            self._last_block_size = ann.block_size
        else:
            self._last_blur_radius = ann.blur_radius
        old_img = self._base
        new_img = bake(self._base, [ann])
        cmd = _BakeDestructiveCommand(self, old_img, new_img, text=ann.kind)
        self._undo_stack.push(cmd)

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

