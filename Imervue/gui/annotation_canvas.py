"""Annotation canvas widget and its add / delete / modify undo commands.

The interactive markup canvas (freehand, shapes, text, mosaic/blur, crop,
selection). Painting, crop, destructive effects and style updates have
dedicated mixins; coordinate and handle calculations live in
``annotation_geometry``. ``annotation_dialog`` re-exports the canvas and
commands for older import sites.
"""
from __future__ import annotations

from collections.abc import Callable

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QImage,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QLineEdit,
    QSizePolicy, QWidget,
)

from Imervue.gui.annotation_models import Annotation
from Imervue.system.qimage_convert import pil_to_qimage
from Imervue.gui.annotation_drawing import AnnotationDrawingMixin
from Imervue.gui.annotation_destructive import AnnotationDestructiveMixin
from Imervue.gui.annotation_crop import AnnotationCropMixin
from Imervue.gui.annotation_style import AnnotationStyleMixin
from Imervue.gui.annotation_hit_test import AnnotationHitTestMixin
from Imervue.gui.annotation_pointer import AnnotationPointerMixin
from Imervue.gui.annotation_input import AnnotationInputMixin
from Imervue.gui.annotation_viewport import AnnotationViewportMixin
from Imervue.gui import annotation_commands as _commands
from Imervue.gui import annotation_geometry as _geometry


_AddAnnotationCommand = _commands._AddAnnotationCommand
_DeleteAnnotationCommand = _commands._DeleteAnnotationCommand
_ModifyAnnotationCommand = _commands._ModifyAnnotationCommand
_fit_display_scale = _geometry.fit_display_scale
_point_segment_distance = _geometry.point_segment_distance


_MODE_RGBA = "RGBA"


class AnnotationCanvas(
        AnnotationPointerMixin, AnnotationHitTestMixin, AnnotationInputMixin,
        AnnotationViewportMixin, AnnotationStyleMixin,
        AnnotationCropMixin, AnnotationDestructiveMixin,
        AnnotationDrawingMixin, QWidget):
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
    save_requested = Signal()
    context_menu_requested = Signal(object)   # a QPoint in global coordinates
    # Emitted when Delete is pressed with no annotation selected — the Modify
    # tab wires this to trash the current image, matching the Imervue tab.
    delete_image_requested = Signal()
    base_changed = Signal()

    def __init__(
            self, base: Image.Image, undo_stack: QUndoStack, parent=None,
            *, full_base_resolver: Callable[[], bool] | None = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 300)

        self._base = base if base.mode == "RGBA" else base.convert("RGBA")
        self._base_qimg = pil_to_qimage(self._base)
        self.full_base_resolver = full_base_resolver
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


    def current_font_family(self) -> str:
        return self._font_family

    def current_font_size(self) -> int:
        return self._font_size

    # ---------- Crop API ----------

    def current_brush_type(self) -> str:
        return self._brush_type

    def current_brush_opacity(self) -> int:
        return self._brush_opacity

    def current_brush_spacing(self) -> int:
        return self._brush_spacing

    def get_base_pil(self) -> Image.Image:
        if not self.ensure_full_base():
            raise ValueError("The current full-quality image is unavailable")
        return self._base

    def ensure_full_base(self) -> bool:
        """Resolve current canonical pixels before a destructive effect or save."""
        return self.full_base_resolver is None or self.full_base_resolver()

    def _set_preview_image(self, geometry_base: Image.Image, qimage: QImage) -> None:
        """Display reduced pixels while coordinates retain full logical geometry."""
        self._base = geometry_base
        self._base_qimg = qimage
        self.update()

    def _set_base_image(self, img: Image.Image, *, qimage: QImage | None = None) -> None:
        """Swap the underlying PIL image (used by _BakeDestructiveCommand
        for undo/redo of mosaic/blur bakes). Callers must own ``img`` —
        we don't copy it here.
        """
        self._base = img if img.mode == "RGBA" else img.convert(_MODE_RGBA)
        self._base_qimg = qimage if qimage is not None else pil_to_qimage(self._base)
        self.update()
        self.base_changed.emit()

    def get_annotations(self) -> list[Annotation]:
        return list(self._annotations)

    def set_annotations(self, anns: list[Annotation]) -> None:
        self._annotations = list(anns)
        self._selected_id = None
        self._undo_stack.clear()
        self.update()


    # (alpha_scale, width_factor) — multiplier applied to stroke_width.
    _BRUSH_PRESETS = {
        "marker":      (0.7, 1.8),
        "pencil":      (0.85, 0.5),
        "highlighter": (0.35, 3.0),
        "watercolor":  (0.2, 2.5),
        "crayon":      (0.8, 1.5),
        "pen":         (1.0, 1.0),
    }

    _handle_positions = staticmethod(_geometry.handle_positions)

    _HANDLE_NAMES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")

    # ---------- Hit testing ----------



    _text_bounding_box = staticmethod(_geometry.text_bounding_box)


    _resize_points = staticmethod(_geometry.resize_points)
