"""PaintCanvas — GPU-accelerated central drawing surface.

Built on QOpenGLWidget so it shares the same hardware-accelerated
texture-quad rendering pattern as
:class:`Imervue.gpu_image_view.gpu_image_view.GPUImageView`, without
inheriting that class's tight coupling to the file-browse model.

For Phase 1 the canvas is wiring only: it loads an image, draws it
under pan / zoom, and routes mouse / tablet events to a registered
tool dispatcher. The actual painting logic is delivered in Phase 2.

Public API:

* :meth:`load_image` — replace the canvas content with an HxWx4 RGBA
  uint8 array (or ``None`` to clear).
* :meth:`set_tool_dispatcher` — install a callable that receives every
  press / move / release; lets the workspace plug different tool
  handlers in without subclassing.
* :attr:`hover_changed` Qt signal — emits ``(x, y)`` in image-space
  pixels (``-1, -1`` when the cursor leaves). The status bar listens.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_LINEAR,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDeleteTextures,
    glEnable,
    glEnd,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glScalef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameterf,
    glTexParameteri,
    glTranslatef,
    glVertex2f,
    glViewport,
    GL_MODELVIEW,
    GL_PROJECTION,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent, QTabletEvent, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

logger = logging.getLogger("Imervue.paint.canvas")

ZOOM_MIN = 0.05
ZOOM_MAX = 32.0
ZOOM_STEP = 1.15


@dataclass
class PointerEvent:
    """Snapshot passed to a tool dispatcher.

    Image-space coordinates may fall outside the canvas bounds when the
    user drags off the edge. Tools can clamp / discard at their
    discretion.
    """

    phase: str            # "press" | "move" | "release" | "leave"
    x: float              # image-space pixel x (float for sub-pixel strokes)
    y: float              # image-space pixel y
    button: int           # Qt.MouseButton value, 0 if no button
    modifiers: int        # Qt.KeyboardModifier flags
    pressure: float       # 0.0..1.0 — 1.0 if no tablet


# A tool dispatcher receives one PointerEvent at a time. Returning ``True``
# tells the canvas to schedule a repaint (so brush previews are visible).
ToolDispatcher = Callable[[PointerEvent], bool]


# ---------------------------------------------------------------------------
# Cursor map — picked up by the workspace whenever the active tool changes.
# Kept module-level so it can be unit-tested without instantiating the GL
# widget (constructing QOpenGLWidget needs a display server).
# ---------------------------------------------------------------------------
_TOOL_CURSORS = {
    "brush": Qt.CursorShape.CrossCursor,
    "eraser": Qt.CursorShape.CrossCursor,
    "fill": Qt.CursorShape.PointingHandCursor,
    "eyedropper": Qt.CursorShape.PointingHandCursor,
    "select_rect": Qt.CursorShape.CrossCursor,
    "select_lasso": Qt.CursorShape.CrossCursor,
    "select_wand": Qt.CursorShape.PointingHandCursor,
    "move": Qt.CursorShape.SizeAllCursor,
    "text": Qt.CursorShape.IBeamCursor,
    "gradient": Qt.CursorShape.CrossCursor,
    "blur": Qt.CursorShape.CrossCursor,
    "smudge": Qt.CursorShape.CrossCursor,
    "hand": Qt.CursorShape.OpenHandCursor,
    "zoom": Qt.CursorShape.PointingHandCursor,
}


def cursor_for_tool(tool: str) -> Qt.CursorShape:
    """Return the documented cursor shape for ``tool``.

    Falls back to :data:`Qt.CursorShape.ArrowCursor` for unknown tools
    so a typo never crashes the canvas — the cursor just doesn't change.
    """
    return _TOOL_CURSORS.get(tool, Qt.CursorShape.ArrowCursor)


def clamp_zoom(value: float) -> float:
    """Clamp a zoom factor into the allowed canvas range."""
    return max(ZOOM_MIN, min(ZOOM_MAX, float(value)))


class PaintCanvas(QOpenGLWidget):
    """GPU canvas for the Paint tab. See module docstring for the API."""

    hover_changed = Signal(int, int)
    image_loaded = Signal(int, int)   # (width, height)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(QCursor(cursor_for_tool("brush")))

        self._image: np.ndarray | None = None
        self._selection: np.ndarray | None = None
        self._texture: int | None = None
        self._needs_upload = False

        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        self._dispatcher: ToolDispatcher | None = None
        self._panning = False
        self._pan_anchor = (0, 0)
        self._last_pressure = 1.0

    # ---- public API ------------------------------------------------------

    def load_image(self, arr: np.ndarray | None) -> None:
        if arr is None:
            self._image = None
            self._selection = None
            self._needs_upload = True
            self.update()
            return
        if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
            raise ValueError(
                f"PaintCanvas.load_image expects HxWx4 uint8 RGBA, "
                f"got {arr.shape} {arr.dtype}",
            )
        self._image = np.ascontiguousarray(arr)
        # Loading a new image always invalidates the previous selection —
        # the mask is per-image and a different shape would be invalid.
        self._selection = None
        self._needs_upload = True
        self._reset_view_to_fit()
        self.image_loaded.emit(arr.shape[1], arr.shape[0])
        self.update()

    def current_image(self) -> np.ndarray | None:
        return self._image

    def current_selection(self) -> np.ndarray | None:
        return self._selection

    def set_selection(self, mask: np.ndarray | None) -> None:
        if mask is None:
            self._selection = None
        else:
            if mask.ndim != 2 or mask.dtype != np.bool_:
                raise ValueError(
                    f"selection mask must be HxW bool, got {mask.shape} {mask.dtype}",
                )
            self._selection = mask
        self.update()

    def set_tool_dispatcher(self, dispatcher: ToolDispatcher | None) -> None:
        self._dispatcher = dispatcher

    def set_cursor_for_tool(self, tool: str) -> None:
        self.setCursor(QCursor(cursor_for_tool(tool)))

    def reset_view(self) -> None:
        self._reset_view_to_fit()
        self.update()

    def zoom_factor(self) -> float:
        return self._zoom

    # ---- GL lifecycle ----------------------------------------------------

    def initializeGL(self) -> None:  # pragma: no cover - GL needs display server
        glClearColor(0.12, 0.12, 0.12, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)

    def resizeGL(self, w: int, h: int) -> None:  # pragma: no cover - GL
        glViewport(0, 0, max(1, w), max(1, h))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, max(1, w), max(1, h), 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self) -> None:  # pragma: no cover - GL needs display server
        glClear(GL_COLOR_BUFFER_BIT)
        if self._image is None:
            return
        if self._needs_upload:
            self._upload_texture()
            self._needs_upload = False
        if self._texture is None:
            return

        h, w = self._image.shape[:2]
        glPushMatrix()
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, 0.0)
        glScalef(self._zoom, self._zoom, 1.0)

        glBindTexture(GL_TEXTURE_2D, self._texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        glPopMatrix()

    # ---- mouse / tablet --------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._is_pan_button(event):
            self._panning = True
            self._pan_anchor = (event.position().x(), event.position().y())
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        self._dispatch("press", event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        x, y = self._screen_to_image(event.position().x(), event.position().y())
        self.hover_changed.emit(int(x), int(y))
        if self._panning:
            dx = event.position().x() - self._pan_anchor[0]
            dy = event.position().y() - self._pan_anchor[1]
            self._pan_anchor = (event.position().x(), event.position().y())
            self._pan_x += dx
            self._pan_y += dy
            self.update()
            return
        self._dispatch("move", event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._panning and self._is_pan_button(event):
            self._panning = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            return
        self._dispatch("release", event)

    def leaveEvent(self, event) -> None:  # pragma: no cover - Qt UI
        self.hover_changed.emit(-1, -1)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # pragma: no cover - Qt UI
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = ZOOM_STEP if delta > 0 else 1.0 / ZOOM_STEP
        self._apply_zoom(factor, event.position().x(), event.position().y())

    def tabletEvent(self, event: QTabletEvent) -> None:  # pragma: no cover - tablet
        # Pen pressure 0..1 — feed through to the next mouse dispatch so
        # the brush can scale size / opacity by it.
        self._last_pressure = float(event.pressure())
        event.accept()

    # ---- internal helpers ------------------------------------------------

    def _dispatch(self, phase: str, event: QMouseEvent) -> None:
        if self._dispatcher is None:
            return
        x, y = self._screen_to_image(event.position().x(), event.position().y())
        evt = PointerEvent(
            phase=phase,
            x=x, y=y,
            button=int(event.button()),
            modifiers=int(event.modifiers()),
            pressure=self._last_pressure,
        )
        if self._dispatcher(evt):
            # The dispatcher mutated the backing array in place — re-upload
            # the texture on the next paint so the change becomes visible.
            self._needs_upload = True
            self.update()

    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom <= 0:
            return (0.0, 0.0)
        x = (sx - self._pan_x) / self._zoom
        y = (sy - self._pan_y) / self._zoom
        return (x, y)

    def _is_pan_button(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.MiddleButton:
            return True
        return bool(
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier,
        )

    def _apply_zoom(self, factor: float, anchor_x: float, anchor_y: float) -> None:
        # Keep the point under the cursor stationary while zooming.
        old_zoom = self._zoom
        new_zoom = clamp_zoom(self._zoom * factor)
        if new_zoom == old_zoom:
            return
        rel_x = (anchor_x - self._pan_x) / old_zoom
        rel_y = (anchor_y - self._pan_y) / old_zoom
        self._zoom = new_zoom
        self._pan_x = anchor_x - rel_x * new_zoom
        self._pan_y = anchor_y - rel_y * new_zoom
        self.update()

    def _reset_view_to_fit(self) -> None:
        if self._image is None:
            return
        h, w = self._image.shape[:2]
        if w <= 0 or h <= 0:
            return
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())
        self._zoom = clamp_zoom(min(widget_w / w, widget_h / h, 1.0))
        self._pan_x = (widget_w - w * self._zoom) * 0.5
        self._pan_y = (widget_h - h * self._zoom) * 0.5

    def _upload_texture(self) -> None:  # pragma: no cover - GL needs display server
        if self._image is None:
            if self._texture is not None:
                glDeleteTextures(1, [self._texture])
                self._texture = None
            return
        if self._texture is None:
            self._texture = int(glGenTextures(1))
        h, w = self._image.shape[:2]
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, self._image.tobytes(),
        )
        glBindTexture(GL_TEXTURE_2D, 0)
