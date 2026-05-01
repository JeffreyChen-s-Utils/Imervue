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
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_LINEAR,
    GL_LINE_LOOP,
    GL_LINE_STRIP,
    GL_LINES,
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
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameterf,
    glTexParameteri,
    glTexSubImage2D,
    glTranslatef,
    glVertex2f,
    glViewport,
    GL_MODELVIEW,
    GL_PROJECTION,
)
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QMouseEvent, QTabletEvent, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument
from Imervue.paint.marquee import selection_outline_segments

logger = logging.getLogger("Imervue.paint.canvas")

ZOOM_MIN = 0.05
ZOOM_MAX = 32.0
ZOOM_STEP = 1.15

DEFAULT_CANVAS_WIDTH = 1024
DEFAULT_CANVAS_HEIGHT = 1024
DEFAULT_CANVAS_FILL = (255, 255, 255, 255)

# QTabletEvent.type() → PointerEvent.phase. Wacom-style stylii deliver
# distinct event types for press / move / release; a missing entry means
# we ignore the event (e.g. ``TabletEnterProximity``).
_TABLET_PHASE = {
    QEvent.Type.TabletPress: "press",
    QEvent.Type.TabletMove: "move",
    QEvent.Type.TabletRelease: "release",
}


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
    # Pen tilt — projection of the stylus onto the canvas plane.
    # 0.0 == perpendicular (no tilt). Mice / fingers always emit 0.0.
    tilt_x: float = 0.0   # -1.0..1.0 — left/right tilt
    tilt_y: float = 0.0   # -1.0..1.0 — up/down tilt


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
    "select_quick": Qt.CursorShape.CrossCursor,
    "move": Qt.CursorShape.SizeAllCursor,
    "text": Qt.CursorShape.IBeamCursor,
    "gradient": Qt.CursorShape.CrossCursor,
    "blur": Qt.CursorShape.CrossCursor,
    "smudge": Qt.CursorShape.CrossCursor,
    "hand": Qt.CursorShape.OpenHandCursor,
    "zoom": Qt.CursorShape.PointingHandCursor,
    "bezier_pen": Qt.CursorShape.CrossCursor,
    "clone_stamp": Qt.CursorShape.CrossCursor,
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


def _wrap_rotation(degrees: float) -> float:
    """Fold a rotation angle into the canonical ``(-180, 180]`` range.

    The view rotation accumulates over multiple ``set_rotation_around_centre``
    calls; without wrapping, an artist who rotates many times in one
    direction would push the field past 360° and surprise downstream
    code that assumes a bounded angle.
    """
    wrapped = ((float(degrees) + 180.0) % 360.0) - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


class PaintCanvas(QOpenGLWidget):
    """GPU canvas for the Paint tab. See module docstring for the API."""

    hover_changed = Signal(int, int)
    image_loaded = Signal(int, int)   # (width, height)
    zoom_changed = Signal(float)      # emitted after wheel / programmatic zoom
    document_changed = Signal()       # emitted when the active layer changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        # Click-focus + keyboard focus so bracket-key brush-size
        # changes (and future shortcut keys) reach this widget without
        # the user having to Tab onto it.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(QCursor(cursor_for_tool("brush")))
        # Drag-and-drop target for the materials dock — drop a tile to
        # spawn a new layer with the material pasted under the cursor.
        # The accept logic lives in :meth:`dragEnterEvent`.
        self.setAcceptDrops(True)

        self._document: PaintDocument = PaintDocument()
        self._texture: int | None = None
        self._needs_upload = False
        # Pending damage rect — when non-empty and not full-frame the
        # next paint uses ``glTexSubImage2D`` for that region instead
        # of the full ``glTexImage2D`` upload.
        self._pending_damage: DamageRect = EMPTY_DAMAGE

        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        # Display rotation in degrees. Affects the GL modelview matrix
        # and screen→image conversion, but never mutates the layer
        # pixels themselves — purely a view transform so the user can
        # spin the canvas under their hand without re-orienting the
        # tablet. Promoted out of the unrotated path so View-menu
        # rotation actions (21d) and Phase 22 paintGL apply uniformly.
        self._rotation_deg = 0.0
        # Overlay flags driven by the View menu (21d). The renderer
        # consults these in ``paintGL`` so subsequent overlay phases
        # (pixel grid, onion skin, bleed guides) can hang their draw
        # calls off the same flag without changing this constructor.
        self._pixel_grid_visible = False
        # Optional brush-size HUD; the workspace assigns a real
        # SizeHudState via ``set_size_hud(state)`` after init so the
        # canvas can render the radius ring on bracket-key changes.
        # Stays ``None`` for canvases used outside the workspace
        # (e.g. unit tests that don't need the HUD overlay).
        self._size_hud = None
        self._tool_state_for_hud = None
        # Optional onion-skin overlay — the workspace sets a callable
        # via ``set_onion_skin_source(callable)`` that returns the
        # HxWx4 RGBA buffer to alpha-blit above the active layer
        # (or ``None`` to skip the overlay this frame).
        self._onion_skin_visible = False
        self._onion_skin_source = None
        self._onion_skin_texture = None
        self._onion_skin_buffer_id = None
        # Bleed guides — paired flag + optional BleedGuides instance.
        # The flag persists across set_bleed_guides() calls so a
        # transient None doesn't reset the user's toggle.
        self._bleed_guides_visible = False
        self._bleed_guides = None
        # Set when ``_reset_view_to_fit`` is called against a widget
        # that's too small to host the document at a sensible zoom
        # (e.g. PaintWorkspace seeding a 1024² blank during ``__init__``
        # before Qt has laid the widget out). The next ``resizeGL`` re-
        # tries the fit so the canvas doesn't permanently appear as a
        # postage stamp clamped to ``ZOOM_MIN``.
        self._fit_pending = False
        # Until the user takes manual view control (wheel-zoom or
        # explicit pan) we keep the canvas auto-fitted to the widget on
        # every resize. Otherwise the layout converging after init
        # (docks settling, tab becoming active) leaves pan / zoom stale
        # for the original size, so a click at the widget centre maps
        # to image coordinates outside the canvas — and the brush silently
        # no-ops because every dab is off-canvas.
        self._user_view_locked = False

        self._dispatcher: ToolDispatcher | None = None
        self._panning = False
        self._pan_anchor = (0, 0)
        self._last_pressure = 1.0

        # Cached marquee segments — recomputed when set_selection() is
        # called, redrawn under an animated phase by _marquee_timer.
        self._marquee_segments: np.ndarray | None = None
        self._marquee_phase = 0
        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(120)
        self._marquee_timer.timeout.connect(self._tick_marquee)
        # Drag-preview overlay set by shape / rect-select tools while a
        # gesture is in flight. Cleared on release. Drawn on top of
        # the document texture so the user can see what they're about
        # to commit before they let go.
        self._tool_overlay: dict | None = None

    # ---- public API ------------------------------------------------------

    def new_blank_document(
        self,
        width: int = DEFAULT_CANVAS_WIDTH,
        height: int = DEFAULT_CANVAS_HEIGHT,
        fill: tuple[int, int, int, int] = DEFAULT_CANVAS_FILL,
    ) -> None:
        """Replace the canvas with a fresh ``height``×``width`` Background
        layer filled with ``fill`` (RGBA, 0–255).

        Without this helper a freshly-constructed PaintCanvas has zero
        layers, so :meth:`current_image` returns ``None`` and the tool
        dispatcher silently no-ops on the first brush stroke. The
        workspace calls this from ``__init__`` so the user can paint
        immediately, matching MediBang's "open with a blank canvas"
        behaviour.
        """
        if width <= 0 or height <= 0:
            raise ValueError(
                f"canvas size must be positive, got {width}×{height}",
            )
        if len(fill) != 4 or any(not 0 <= int(c) <= 255 for c in fill):
            raise ValueError(
                f"fill must be a 4-tuple of 0..255 ints, got {fill!r}",
            )
        arr = np.empty((int(height), int(width), 4), dtype=np.uint8)
        arr[..., :] = fill
        self.load_image(arr)

    def load_image(self, arr: np.ndarray | None) -> None:
        """Replace the canvas with a single-layer document of ``arr``.

        ``None`` clears the document — the canvas paints empty until
        another image is loaded.
        """
        if arr is None:
            self._document = PaintDocument()
            self._needs_upload = True
            self._pending_damage = EMPTY_DAMAGE
            self._marquee_segments = None
            self._marquee_timer.stop()
            self._user_view_locked = False
            self._rotation_deg = 0.0
            self.update()
            return
        if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
            raise ValueError(
                f"PaintCanvas.load_image expects HxWx4 uint8 RGBA, "
                f"got {arr.shape} {arr.dtype}",
            )
        self._document = PaintDocument()
        self._document.load_image(arr)
        self._marquee_segments = None
        self._marquee_timer.stop()
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        self._user_view_locked = False
        self._reset_view_to_fit()
        self.image_loaded.emit(arr.shape[1], arr.shape[0])
        self.document_changed.emit()
        self.update()

    def document(self) -> PaintDocument:
        return self._document

    def current_image(self) -> np.ndarray | None:
        """Return the *active layer's* image — the buffer tools paint into.

        Returning the active layer (rather than the composited frame)
        is what makes layer-aware painting work: every tool mutates the
        active layer in place, and the canvas re-composites on the
        next paint.
        """
        layer = self._document.active_layer()
        return None if layer is None else layer.image

    def current_selection(self) -> np.ndarray | None:
        return self._document.selection()

    def invalidate_texture(self) -> None:
        """Mark the GL texture for full re-upload on the next paint.

        Used after wholesale document mutations (undo / redo, file
        load) so the canvas's GL texture reflects the new pixels
        instead of the previous frame's cache.
        """
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE

    def set_selection(self, mask: np.ndarray | None) -> None:
        if mask is not None and (mask.ndim != 2 or mask.dtype != np.bool_):
            raise ValueError(
                f"selection mask must be HxW bool, got {mask.shape} {mask.dtype}",
            )
        self._document.set_selection(mask)
        if mask is None:
            self._marquee_segments = None
            self._marquee_timer.stop()
        else:
            self._marquee_segments = selection_outline_segments(mask)
            if self._marquee_segments.shape[0] > 0:
                self._marquee_timer.start()
            else:
                self._marquee_timer.stop()
        self.update()

    def set_tool_dispatcher(self, dispatcher: ToolDispatcher | None) -> None:
        self._dispatcher = dispatcher

    def set_tool_overlay(self, overlay: dict | None) -> None:
        """Set or clear the active tool's drag-preview overlay.

        ``overlay`` is a small dict telling the canvas what shape to
        outline above the document texture:

        * ``{"kind": "rect", "x0": ..., "y0": ..., "x1": ..., "y1": ...}``
        * ``{"kind": "ellipse", "cx": ..., "cy": ..., "rx": ..., "ry": ...}``
        * ``{"kind": "line", "x0": ..., "y0": ..., "x1": ..., "y1": ...}``
        * ``{"kind": "polyline", "points": [(x, y), ...]}``

        Pass ``None`` to clear. Tools call this on press / move and
        clear on release; the canvas calls ``update`` so the overlay
        repaints on the next event-loop tick.
        """
        self._tool_overlay = overlay
        self.update()

    def set_cursor_for_tool(self, tool: str) -> None:
        self.setCursor(QCursor(cursor_for_tool(tool)))

    def reset_view(self) -> None:
        # Explicit "fit to window" — re-enable auto-fit so subsequent
        # window resizes keep the canvas centred until the user wheels
        # / pans again.
        self._user_view_locked = False
        self._reset_view_to_fit()
        self.update()

    def zoom_factor(self) -> float:
        return self._zoom

    def set_bleed_guides(self, guides) -> None:
        """Wire a :class:`Imervue.paint.bleed_guides.BleedGuides`
        instance the canvas should overlay above the layer composite.

        ``None`` clears the guides; the visibility flag is preserved
        so a later ``set_bleed_guides(g)`` re-shows them.
        """
        self._bleed_guides = guides
        self.update()

    def set_bleed_guides_visible(self, visible: bool) -> None:
        """Toggle bleed-guide overlay visibility; repaints the canvas."""
        new_value = bool(visible)
        if new_value == self._bleed_guides_visible:
            return
        self._bleed_guides_visible = new_value
        self.update()

    def set_onion_skin_visible(self, visible: bool) -> None:
        """Toggle the onion-skin overlay; repaints the canvas."""
        new_value = bool(visible)
        if new_value == self._onion_skin_visible:
            return
        self._onion_skin_visible = new_value
        self.update()

    def set_onion_skin_source(self, callable_or_none) -> None:
        """Wire the onion-skin overlay's pixel source.

        ``callable_or_none`` is a zero-arg callable that returns the
        current overlay buffer (HxWx4 uint8 RGBA matching the
        document shape) or ``None`` to skip the overlay this frame.
        Stored verbatim so callers can swap the source mid-session
        (e.g. when the active animation changes).
        """
        self._onion_skin_source = callable_or_none
        self._onion_skin_texture = None   # force re-upload of new buffers
        self._onion_skin_buffer_id = None

    def set_size_hud(self, hud, tool_state) -> None:
        """Wire the brush-size HUD overlay.

        ``hud`` is a :class:`Imervue.paint.size_hud.SizeHudState`
        and ``tool_state`` is the workspace's :class:`ToolState`.
        Both are stashed; the bracket-key handler in
        ``keyPressEvent`` consults them to bump the brush size and
        flash the HUD.
        """
        self._size_hud = hud
        self._tool_state_for_hud = tool_state

    def set_pixel_grid_visible(self, visible: bool) -> None:
        """Toggle the pixel-grid overlay; repaints the canvas.

        The overlay only renders if the zoom is past
        :data:`Imervue.paint.visual_guides.PIXEL_GRID_MIN_ZOOM` —
        below that the grid would crowd the underlying pixels and
        the user gets moiré rather than guidance.
        """
        new_value = bool(visible)
        if new_value == self._pixel_grid_visible:
            return
        self._pixel_grid_visible = new_value
        self.update()

    def should_paint_pixel_grid(self) -> bool:
        """Pure-logic predicate the GL paint path consults.

        Exposed for unit testing because ``paintGL`` itself can't be
        exercised without a display server.
        """
        from Imervue.paint.visual_guides import should_show_pixel_grid
        return self._pixel_grid_visible and should_show_pixel_grid(self._zoom)

    def rotation_degrees(self) -> float:
        """Return the current view rotation in degrees."""
        return float(self._rotation_deg)

    def set_canvas_rotation(self, degrees: float) -> None:
        """Set the view rotation absolutely. Repaints; never mutates pixels."""
        wrapped = _wrap_rotation(float(degrees))
        if wrapped == self._rotation_deg:
            return
        self._rotation_deg = wrapped
        self._user_view_locked = True
        self.update()

    def set_rotation_around_centre(
        self, anchor_zoom: float, delta_deg: float,
    ) -> None:
        """Rotate the view by ``delta_deg`` keeping the widget centre fixed.

        ``anchor_zoom`` is informational — the widget centre is the
        anchor in screen space; the maths reduces to a simple delta
        because rotating about the visual midpoint doesn't shift it.
        Pan stays valid because the rotation pivots about the centre,
        not about an off-centre image-space point.
        """
        del anchor_zoom   # accepted for callsite stability; unused
        new_rotation = _wrap_rotation(self._rotation_deg + float(delta_deg))
        if new_rotation == self._rotation_deg:
            return
        self._rotation_deg = new_rotation
        self._user_view_locked = True
        self.update()

    def set_zoom(self, factor: float) -> None:
        """Programmatic zoom — pivots about the widget centre.

        Used by the Navigator dock's zoom slider. Marks the view as
        user-controlled so subsequent window resizes don't auto-fit
        away the chosen zoom.
        """
        target = clamp_zoom(factor)
        if target == self._zoom:
            return
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())
        anchor_x = widget_w * 0.5
        anchor_y = widget_h * 0.5
        rel_x = (anchor_x - self._pan_x) / self._zoom
        rel_y = (anchor_y - self._pan_y) / self._zoom
        self._zoom = target
        self._pan_x = anchor_x - rel_x * target
        self._pan_y = anchor_y - rel_y * target
        self._user_view_locked = True
        self.zoom_changed.emit(target)
        self.update()

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
        # Re-fit on every resize until the user manually controls the
        # view. ``_fit_pending`` covers the deferred-init case (widget
        # was too small earlier); ``_user_view_locked`` is the user-took-
        # control flag that pins the view once they wheel-zoom or pan.
        if self._fit_pending or not self._user_view_locked:
            self._reset_view_to_fit()

    def paintGL(self) -> None:  # pragma: no cover - GL needs display server
        glClear(GL_COLOR_BUFFER_BIT)
        composite = self._document.composite()
        if composite is None:
            return
        # Recovery path for the deferred-fit case: when ``new_blank_document``
        # was called before Qt sized the widget, ``_fit_pending`` stayed
        # True. Some Qt builds don't fire a follow-up ``resizeGL`` between
        # the first valid layout and the first paint, leaving the canvas
        # off-centre. Retry here whenever a paint happens with widths
        # finally available.
        if self._fit_pending and self.width() > 0 and self.height() > 0:
            self._reset_view_to_fit()
        if self._needs_upload:
            self._upload_texture(composite)
            self._needs_upload = False
        if self._texture is None:
            return

        h, w = composite.shape[:2]
        glPushMatrix()
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, 0.0)
        glScalef(self._zoom, self._zoom, 1.0)
        # Rotation pivots about the canvas centre so the visual mid
        # stays put — matches the screen↔image conversion math in
        # ``_screen_to_image`` and the View-menu rotate action.
        if self._rotation_deg != 0.0:
            glTranslatef(w / 2.0, h / 2.0, 0.0)
            glRotatef(self._rotation_deg, 0.0, 0.0, 1.0)
            glTranslatef(-w / 2.0, -h / 2.0, 0.0)

        # White paper underneath the document texture so erased
        # (alpha=0) areas show the paint-app-standard "white paper"
        # rather than the editor's dark backdrop. Drawn UNTEXTURED
        # so the rest of the GL widget (outside the canvas extent)
        # keeps the dark grey backdrop set by ``glClearColor``.
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glVertex2f(0.0, 0.0)
        glVertex2f(w, 0.0)
        glVertex2f(w, h)
        glVertex2f(0.0, h)
        glEnd()
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        if self._onion_skin_visible:
            self._draw_onion_skin(w, h)
        if self.should_paint_pixel_grid():
            self._draw_pixel_grid(w, h)
        if self._bleed_guides_visible and self._bleed_guides is not None:
            self._draw_bleed_guides()
        self._draw_marquee()
        if self._tool_overlay is not None:
            self._draw_tool_overlay()
        glPopMatrix()
        # HUD overlay sits in widget-space (un-rotated) so the user
        # always sees a circular ring at the canvas centre regardless
        # of the canvas rotation. Drawn AFTER popping the modelview.
        if self._size_hud is not None:
            self._draw_size_hud()

    def _draw_marquee(self) -> None:  # pragma: no cover - GL needs display server
        """Draw the active selection outline as marching ants.

        Two passes — one in white, one in black — offset by the
        marquee phase so successive frames look like the dashes are
        marching along the boundary. Disabling the texture target
        during line drawing avoids the line colour multiplying with
        whatever was last bound.
        """
        if self._marquee_segments is None or self._marquee_segments.shape[0] == 0:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0)
        # Sample every other segment for each colour pass — the offset
        # walk produces the marching effect on consecutive frames.
        seg = self._marquee_segments
        white_idx = (np.arange(seg.shape[0]) + self._marquee_phase) % 4 < 2
        self._draw_segments(seg[white_idx], 1.0, 1.0, 1.0)
        self._draw_segments(seg[~white_idx], 0.0, 0.0, 0.0)
        glEnable(GL_TEXTURE_2D)

    @staticmethod
    def _draw_segments(  # pragma: no cover - GL needs display server
        seg: np.ndarray, r: float, g: float, b: float,
    ) -> None:
        if seg.shape[0] == 0:
            return
        glColor4f(r, g, b, 1.0)
        glBegin(GL_LINES)
        for x0, y0, x1, y1 in seg:
            glVertex2f(float(x0), float(y0))
            glVertex2f(float(x1), float(y1))
        glEnd()

    def _tick_marquee(self) -> None:
        self._marquee_phase = (self._marquee_phase + 1) % 8
        self.update()

    def _draw_tool_overlay(self) -> None:  # pragma: no cover - GL needs display
        """Stroke the drag-preview shape set by the active tool.

        Lines are drawn at zoom-compensated width so the outline is
        always 1 screen-pixel thick regardless of canvas zoom.
        """
        overlay = self._tool_overlay
        if not overlay:
            return
        kind = overlay.get("kind")
        glDisable(GL_TEXTURE_2D)
        glLineWidth(max(1.0, 1.0 / max(self._zoom, 1e-3)))
        glColor4f(0.0, 0.0, 0.0, 0.7)
        if kind == "rect":
            x0 = float(overlay["x0"])
            y0 = float(overlay["y0"])
            x1 = float(overlay["x1"])
            y1 = float(overlay["y1"])
            glBegin(GL_LINE_LOOP)
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
            glEnd()
        elif kind == "ellipse":
            cx = float(overlay["cx"])
            cy = float(overlay["cy"])
            rx = float(overlay["rx"])
            ry = float(overlay["ry"])
            segments = 64
            glBegin(GL_LINE_LOOP)
            for i in range(segments):
                theta = 2.0 * math.pi * i / segments
                glVertex2f(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            glEnd()
        elif kind == "line":
            glBegin(GL_LINES)
            glVertex2f(float(overlay["x0"]), float(overlay["y0"]))
            glVertex2f(float(overlay["x1"]), float(overlay["y1"]))
            glEnd()
        elif kind == "polyline":
            points = overlay.get("points", ())
            if len(points) >= 2:
                glBegin(GL_LINE_STRIP)
                for x, y in points:
                    glVertex2f(float(x), float(y))
                glEnd()
        glEnable(GL_TEXTURE_2D)

    def _draw_bleed_guides(self) -> None:  # pragma: no cover - GL needs display
        """Stroke the trim / bleed / safe rects from the active
        :class:`BleedGuides` over the layer composite.

        Three distinct colours so the user can tell the rects
        apart at a glance — bleed (red, outermost), trim (cyan,
        the printed boundary), safe (yellow, innermost).
        """
        guides = self._bleed_guides
        if guides is None:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0 / max(self._zoom, 1e-3) + 1.0)
        for rect, colour in (
            (guides.bleed_rect_px(), (1.0, 0.2, 0.2, 0.85)),
            (guides.trim_rect_px(), (0.2, 0.9, 1.0, 0.85)),
            (guides.safe_rect_px(), (1.0, 0.95, 0.2, 0.85)),
        ):
            x, y, w_px, h_px = rect
            glColor4f(*colour)
            glBegin(GL_LINES)
            for x0, y0, x1, y1 in (
                (x, y, x + w_px, y),
                (x + w_px, y, x + w_px, y + h_px),
                (x + w_px, y + h_px, x, y + h_px),
                (x, y + h_px, x, y),
            ):
                glVertex2f(float(x0), float(y0))
                glVertex2f(float(x1), float(y1))
            glEnd()
        glLineWidth(1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_onion_skin(  # pragma: no cover - GL needs display
        self, w: int, h: int,
    ) -> None:
        """Blit the onion-skin overlay buffer above the layer composite.

        Uploads the source buffer as a separate GL texture so the
        layer-composite texture isn't disturbed; re-upload only
        fires when the source returns a different ndarray (compared
        by ``id()``) so a steady-state animation doesn't churn the
        texture every frame.
        """
        if self._onion_skin_source is None:
            return
        try:
            buffer = self._onion_skin_source()
        except (ValueError, RuntimeError):
            return
        if buffer is None:
            return
        if (
            buffer.ndim != 3
            or buffer.shape[2] != 4
            or buffer.dtype != np.uint8
        ):
            return
        bh, bw = buffer.shape[:2]
        if (bh, bw) != (h, w):
            return
        # Upload only when the buffer object actually changed.
        if id(buffer) != self._onion_skin_buffer_id:
            if self._onion_skin_texture is None:
                self._onion_skin_texture = int(glGenTextures(1))
            glBindTexture(GL_TEXTURE_2D, self._onion_skin_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, bw, bh, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, buffer.tobytes(),
            )
            self._onion_skin_buffer_id = id(buffer)
        glBindTexture(GL_TEXTURE_2D, self._onion_skin_texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)

    def _draw_size_hud(self) -> None:  # pragma: no cover - GL needs display
        """Render the brush-size HUD ring at the canvas centre.

        Two passes (black shadow + white foreground) for legibility
        against any underlying composite. Alpha follows the HUD
        state's decay curve; 0 short-circuits without any GL calls
        so an idle canvas never pays the per-frame overhead.
        """
        import time
        alpha = self._size_hud.alpha_at(now=time.monotonic())
        if alpha <= 0.0:
            return
        if self._tool_state_for_hud is None:
            return
        radius = float(self._tool_state_for_hud.brush.size) * self._zoom * 0.5
        if radius <= 0:
            return
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        # Schedule another paint while the HUD is fading so the
        # animation doesn't stall mid-fade after the user releases
        # the bracket key.
        if alpha > 0.0:
            self.update()
        # Draw a circle outline by stepping through angles. 64 steps
        # gives a smooth-enough ring at typical brush sizes; the
        # HUD never needs higher fidelity than the cursor outline.
        glDisable(GL_TEXTURE_2D)
        steps = 64
        # Black shadow (1 px outside the white ring) for readability.
        glLineWidth(2.0)
        glColor4f(0.0, 0.0, 0.0, alpha * 0.7)
        glBegin(GL_LINES)
        for i in range(steps):
            t0 = (i / steps) * 2.0 * math.pi
            t1 = ((i + 1) / steps) * 2.0 * math.pi
            glVertex2f(cx + (radius + 1) * math.cos(t0),
                       cy + (radius + 1) * math.sin(t0))
            glVertex2f(cx + (radius + 1) * math.cos(t1),
                       cy + (radius + 1) * math.sin(t1))
        glEnd()
        glLineWidth(1.0)
        glColor4f(1.0, 1.0, 1.0, alpha)
        glBegin(GL_LINES)
        for i in range(steps):
            t0 = (i / steps) * 2.0 * math.pi
            t1 = ((i + 1) / steps) * 2.0 * math.pi
            glVertex2f(cx + radius * math.cos(t0),
                       cy + radius * math.sin(t0))
            glVertex2f(cx + radius * math.cos(t1),
                       cy + radius * math.sin(t1))
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _draw_pixel_grid(  # pragma: no cover - GL needs display server
        self, w: int, h: int,
    ) -> None:
        """Draw a 1-image-pixel grid overlay above the layer composite.

        At zoom levels past PIXEL_GRID_MIN_ZOOM each image pixel
        occupies enough widget pixels for a 1-px grid to read as
        guidance rather than noise. The line width is fixed at the
        GL default (1 px in the modelview-scaled space) so heavier
        zoom doesn't bloat the lines into solid bands.
        """
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0 / max(self._zoom, 1e-3))
        glColor4f(0.5, 0.5, 0.5, 0.5)
        glBegin(GL_LINES)
        for x in range(int(w) + 1):
            glVertex2f(float(x), 0.0)
            glVertex2f(float(x), float(h))
        for y in range(int(h) + 1):
            glVertex2f(0.0, float(y))
            glVertex2f(float(w), float(y))
        glEnd()
        glLineWidth(1.0)
        glEnable(GL_TEXTURE_2D)

    # ---- mouse / tablet --------------------------------------------------

    def keyPressEvent(self, event) -> None:  # pragma: no cover - Qt UI
        """Bracket-key brush size + Enter pen-commit + HUD flash."""
        from PySide6.QtCore import Qt as _Qt
        key = event.key()
        if key in (_Qt.Key.Key_BracketLeft, _Qt.Key.Key_BracketRight):
            if self._tool_state_for_hud is None or self._size_hud is None:
                event.ignore()
                return
            from Imervue.paint.size_hud_bridge import (
                adjust_brush_size, trigger_size_hud,
            )
            adjust_brush_size(
                self._tool_state_for_hud,
                larger=(key == _Qt.Key.Key_BracketRight),
            )
            trigger_size_hud(self._tool_state_for_hud, self._size_hud)
            self.update()
            return
        if key in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter):
            workspace = self._workspace_for_pen_commit()
            if workspace is None:
                event.ignore()
                return
            from Imervue.paint.pen_commit import commit_pen_path
            if commit_pen_path(workspace):
                self._needs_upload = True
                self.document_changed.emit()
                self.update()
            return
        super().keyPressEvent(event)

    def _workspace_for_pen_commit(self):
        """Return the workspace if it owns a bezier pen path.

        The canvas doesn't import :class:`PaintWorkspace` directly to
        avoid a circular dependency; instead it duck-types on the
        ``_bezier_pen_path`` attribute the pen tool stores.
        """
        candidate = self.parent()
        for _ in range(4):   # walk up at most a few parents
            if candidate is None:
                break
            if hasattr(candidate, "_bezier_pen_path"):
                return candidate
            candidate = candidate.parent() if hasattr(candidate, "parent") else None
        return None

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
            # Manual pan — stop auto-fitting on subsequent resizes.
            self._user_view_locked = True
            self.update()
            return
        self._dispatch("move", event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover - Qt UI
        if self._panning and self._is_pan_button(event):
            self._panning = False
            # Restore the active tool's cursor — the open-hand was only
            # valid while the pan gesture was active. Falling back to
            # "brush" when the workspace hasn't installed a tool-state
            # is safer than leaving the closed-hand stuck.
            active_tool = (
                self._tool_state_for_hud.tool
                if self._tool_state_for_hud is not None
                else "brush"
            )
            self.set_cursor_for_tool(active_tool)
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
        # ``event.accept()`` suppresses Qt's synthesised mouse event,
        # so the brush would receive nothing if we only stored pressure
        # here — that is the original "下筆後沒顏色" symptom for tablet
        # users. Map the tablet event onto the same dispatch path used
        # by mouse input so press / move / release reach the active
        # tool with full pressure + tilt detail.
        self._last_pressure = float(event.pressure())
        phase = _TABLET_PHASE.get(event.type())
        if phase is not None:
            self._dispatch_pointer(
                phase,
                event.position().x(), event.position().y(),
                button=int(event.button().value),
                modifiers=int(event.modifiers().value),
                pressure=self._last_pressure,
                tilt_x=float(event.xTilt()) / 60.0,
                tilt_y=float(event.yTilt()) / 60.0,
            )
        event.accept()

    # ---- internal helpers ------------------------------------------------

    def _dispatch(self, phase: str, event: QMouseEvent) -> None:
        # PySide6 6.x returns Qt.MouseButton / Qt.KeyboardModifier as
        # flag enums that don't auto-convert via int() — go through
        # ``.value`` so PointerEvent stays plain-int as the tests expect.
        self._dispatch_pointer(
            phase,
            event.position().x(), event.position().y(),
            button=int(event.button().value),
            modifiers=int(event.modifiers().value),
            pressure=self._last_pressure,
        )

    def _dispatch_pointer(
        self,
        phase: str,
        x_screen: float,
        y_screen: float,
        *,
        button: int,
        modifiers: int,
        pressure: float,
        tilt_x: float = 0.0,
        tilt_y: float = 0.0,
    ) -> None:
        """Shared mouse / tablet entry into the tool dispatcher.

        Translates screen coordinates into image space, builds the
        immutable :class:`PointerEvent`, hands it to the active tool,
        and refreshes the canvas only when the tool reported a change.
        """
        if self._dispatcher is None:
            return
        x, y = self._screen_to_image(x_screen, y_screen)
        evt = PointerEvent(
            phase=phase,
            x=x, y=y,
            button=button,
            modifiers=modifiers,
            pressure=pressure,
            tilt_x=max(-1.0, min(1.0, tilt_x)),
            tilt_y=max(-1.0, min(1.0, tilt_y)),
        )
        if self._dispatcher(evt):
            # The dispatcher mutated the active layer in place — drop the
            # cached composite and re-upload the texture on the next paint
            # so the change becomes visible. ``last_damage`` (when the
            # dispatcher exposes it) lets us shrink the upload to the
            # touched region; tools without damage tracking fall back
            # to a full-frame upload.
            self._document.invalidate_composite()
            self._needs_upload = True
            damage = getattr(self._dispatcher, "last_damage", None)
            if isinstance(damage, DamageRect) and not damage.is_empty:
                self._pending_damage = self._pending_damage.union(damage)
            else:
                self._pending_damage = EMPTY_DAMAGE
            self.document_changed.emit()
            self.update()

    # ---- material drag-drop ---------------------------------------------

    def dragEnterEvent(self, event) -> None:  # pragma: no cover - Qt UI
        from Imervue.paint.material_drop import MATERIAL_MIME_TYPE
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return
        if mime.hasFormat(MATERIAL_MIME_TYPE) or mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # pragma: no cover - Qt UI
        # Re-affirm on every move so Qt keeps showing the move cursor.
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # pragma: no cover - Qt UI
        from Imervue.paint.material_drop import (
            MATERIAL_MIME_TYPE,
            commit_material_to_document,
            load_material_image,
        )
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return
        path: str | None = None
        if mime.hasFormat(MATERIAL_MIME_TYPE):
            blob = mime.data(MATERIAL_MIME_TYPE)
            try:
                path = bytes(blob.data()).decode("utf-8")
            except UnicodeDecodeError:
                path = None
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    break
        if not path:
            event.ignore()
            return
        try:
            tile = load_material_image(path)
        except (FileNotFoundError, OSError, ValueError):
            event.ignore()
            return
        pos = event.position() if hasattr(event, "position") else event.pos()
        sx = float(pos.x())
        sy = float(pos.y())
        ix, iy = self._screen_to_image(sx, sy)
        commit_material_to_document(
            self._document, tile,
            drop_x=int(round(ix)), drop_y=int(round(iy)),
        )
        self.document_changed.emit()
        self._needs_upload = True
        self.update()
        event.acceptProposedAction()

    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom <= 0:
            return (0.0, 0.0)
        # Undo pan + zoom first; then unwind the view rotation around
        # the canvas's image-space midpoint so a rotated canvas still
        # routes brush dabs onto the pixel under the cursor.
        rel_x = (sx - self._pan_x) / self._zoom
        rel_y = (sy - self._pan_y) / self._zoom
        if self._rotation_deg == 0.0:
            return (rel_x, rel_y)
        shape = self._document.shape
        if shape is None:
            return (rel_x, rel_y)
        h, w = shape
        cx = float(w) / 2.0
        cy = float(h) / 2.0
        rad = math.radians(-self._rotation_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        dx = rel_x - cx
        dy = rel_y - cy
        return (cx + dx * cos_a - dy * sin_a,
                cy + dx * sin_a + dy * cos_a)

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
        # User wheel-zoomed — stop auto-fitting on subsequent resizes.
        self._user_view_locked = True
        self.zoom_changed.emit(new_zoom)
        self.update()

    def _reset_view_to_fit(self) -> None:
        shape = self._document.shape
        if shape is None:
            return
        h, w = shape
        if w <= 0 or h <= 0:
            return
        widget_w = self.width()
        widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            self._fit_pending = True
            return
        raw_zoom = min(widget_w / w, widget_h / h, 1.0)
        if raw_zoom <= ZOOM_MIN:
            # Widget too small (or document oversized) — defer to the
            # next resizeGL so the canvas doesn't lock at the floor zoom.
            self._fit_pending = True
            return
        self._zoom = clamp_zoom(raw_zoom)
        self._pan_x = (widget_w - w * self._zoom) * 0.5
        self._pan_y = (widget_h - h * self._zoom) * 0.5
        self._fit_pending = False

    def _upload_texture(  # pragma: no cover - GL needs display server
        self, composite: np.ndarray,
    ) -> None:
        if composite is None:
            if self._texture is not None:
                glDeleteTextures(1, [self._texture])
                self._texture = None
            return
        h, w = composite.shape[:2]
        first_upload = self._texture is None
        if first_upload:
            self._texture = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._texture)
        if first_upload:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        damage = self._pending_damage.clipped_to((h, w))
        if (
            first_upload
            or damage.is_empty
            or damage.covers_full((h, w))
        ):
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, composite.tobytes(),
            )
        else:
            # Sub-region upload — only the dirty pixels move across
            # the bus. The slice is materialised into a packed buffer
            # via ``ascontiguousarray`` so the bytes handed to OpenGL
            # are exactly damage.h * damage.w * 4 long; we therefore
            # leave UNPACK_ROW_LENGTH at the default (0 = packed
            # rows). Setting it to ``w`` here would tell GL that each
            # source row is the full canvas wide and trigger a read
            # past the end of the packed buffer.
            sub = np.ascontiguousarray(
                composite[damage.y:damage.y2, damage.x:damage.x2, :],
            )
            glTexSubImage2D(
                GL_TEXTURE_2D, 0,
                damage.x, damage.y, damage.w, damage.h,
                GL_RGBA, GL_UNSIGNED_BYTE,
                sub.tobytes(),
            )
        glBindTexture(GL_TEXTURE_2D, 0)
        self._pending_damage = EMPTY_DAMAGE
