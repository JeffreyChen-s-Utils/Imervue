"""Crop interaction of the annotation canvas.

The crop tool's state (rectangle, aspect ratio) and mouse handling: pressing
starts a new rectangle, moves it or grabs one of its eight handles, dragging
updates it with the ratio enforced and the rectangle kept inside the image,
and releasing finishes the drag. Painting the overlay lives in
``annotation_drawing``; ``AnnotationCanvas`` mixes these methods in.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt

from Imervue.gui.annotation_drawing import HANDLE_SIZE
from Imervue.gui.annotation_models import TOOL_MOVE


def handle_cursor(handle: str) -> Qt.CursorShape:
    """Resize cursor for a crop or annotation handle name (``"nw"``, ``"e"``, ...)."""
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


class AnnotationCropMixin:
    """Crop-tool state and mouse handling of the annotation canvas."""

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

    def _crop_hit_handle(self, pt: QPointF) -> str | None:
        """Check if pt hits a handle on the current crop rect."""
        if self._crop_rect is None:
            return None
        cx, cy, cw, ch = self._crop_rect
        crop_screen = QRectF(
            self._image_to_screen(cx, cy),
            self._image_to_screen(cx + cw, cy + ch),
        ).normalized()
        h = HANDLE_SIZE
        for name, (hx, hy) in zip(
            self._HANDLE_NAMES, self._handle_positions(crop_screen), strict=False,
        ):
            box = QRectF(hx - h, hy - h, h * 2, h * 2)
            if box.contains(pt):
                return name
        # Inside crop rect = move
        if crop_screen.contains(pt):
            return TOOL_MOVE
        return None

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
            elif self._crop_drag_handle == TOOL_MOVE and self._crop_drag_orig:
                self._crop_drag_move(sx, sy, ix, iy)
            elif self._crop_drag_orig:
                self._crop_drag_resize(sx, sy, ix, iy)
            self.update()
            return
        handle = self._crop_hit_handle(pt) if self._crop_rect else None
        if handle is not None and handle != TOOL_MOVE:
            self.setCursor(handle_cursor(handle))
        elif handle == TOOL_MOVE:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

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
