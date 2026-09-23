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

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_LINEAR,
    GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_REPEAT,
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
from OpenGL.error import GLError
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument
from Imervue.paint.marquee import selection_outline_segments
from Imervue.paint.pointer_event import PointerEvent, ToolDispatcher
from Imervue.paint.canvas_overlays import PaintCanvasOverlaysMixin, build_checker_pattern
from Imervue.paint.canvas_input import PaintCanvasInputMixin
from Imervue.paint.canvas_view import ZOOM_MAX, ZOOM_MIN, PaintCanvasViewMixin, clamp_zoom

# Other modules and the tests import these from here; the pointer event lives
# in ``pointer_event`` and the checker pattern in ``canvas_overlays``.
__all__ = [
    "ZOOM_MAX",
    "ZOOM_MIN",
    "PaintCanvas",
    "PointerEvent",
    "ToolDispatcher",
    "build_checker_pattern",
    "clamp_zoom",
    "cursor_for_tool",
]

logger = logging.getLogger("Imervue.paint.canvas")


DEFAULT_CANVAS_WIDTH = 1024
DEFAULT_CANVAS_HEIGHT = 1024
DEFAULT_CANVAS_FILL = (255, 255, 255, 255)


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
    "dodge": Qt.CursorShape.CrossCursor,
    "burn": Qt.CursorShape.CrossCursor,
    "sponge": Qt.CursorShape.CrossCursor,
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


class PaintCanvas(
        PaintCanvasViewMixin, PaintCanvasInputMixin, PaintCanvasOverlaysMixin,
        QOpenGLWidget):
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
        # Custom context menu — the workspace listens to this signal
        # via ``customContextMenuRequested`` and pops a Photoshop-
        # style quick-actions menu (undo / redo / select all / fit).
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Drag-and-drop target for the materials dock — drop a tile to
        # spawn a new layer with the material pasted under the cursor.
        # The accept logic lives in :meth:`dragEnterEvent`.
        self.setAcceptDrops(True)

        self._init_document_and_gl_state()
        self._init_view_state()
        self._init_interaction_state()

    def _init_document_and_gl_state(self) -> None:
        """Document subscription plus the GL textures, upload flags and grid VBO cache."""
        self._document: PaintDocument = PaintDocument()
        # Subscribe so wholesale document mutations (add layer, set
        # layer attribute, invalidate composite, etc.) force a full
        # texture re-upload on the next paint. Brush strokes mutate
        # layer.image in place without firing _notify, so this
        # subscription doesn't interfere with the dispatcher's
        # damage-rect-based incremental upload path.
        self._document_unsubscribe = self._document.listen(
            self._on_document_changed,
        )
        self._texture: int | None = None
        # Tiled checker texture rendered behind the layer composite so
        # alpha=0 areas read as the standard "transparency checker"
        # pattern (Photoshop /  / raster paint apps convention) instead
        # of either the editor's dark backdrop or a flat white sheet.
        # Built lazily on first paint because the GL context isn't
        # current during ``__init__``.
        self._checker_texture: int | None = None
        # ``True`` while a material / file drag is hovering over the
        # canvas. Drives the blue tint + thick border ``paintGL``
        # overlay so the user sees that the canvas is the active
        # drop target before they release the mouse.
        self._drag_overlay_active = False
        self._needs_upload = False
        # Pending damage rect — when non-empty and not full-frame the
        # next paint uses ``glTexSubImage2D`` for that region instead
        # of the full ``glTexImage2D`` upload.
        self._pending_damage: DamageRect = EMPTY_DAMAGE
        # Pixel-grid VBO cache. Each entry is keyed by ``(w, h)`` and
        # holds the GL buffer id plus its vertex count. The grid is
        # rebuilt only when the canvas dimensions change — the
        # previous implementation issued ~(w+h)*2 ``glVertex2f`` calls
        # per frame, which became visible in profiles at deep-zoom on
        # large documents.
        self._grid_vbo: int | None = None
        self._grid_vbo_size: tuple[int, int] | None = None
        self._grid_vbo_vertices: int = 0

    def _init_view_state(self) -> None:
        """Zoom, pan, rotation, overlay toggles and the auto-fit bookkeeping."""
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
        # Widget size at the last successful fit. Used by paintGL's
        # auto-refit safety net so the canvas re-centres when Qt's
        # layout converges to a larger size after the first resizeGL.
        self._fitted_widget_size: tuple[int, int] = (0, 0)
        # Most-recent ``resizeGL`` size. Used by ``_reset_view_to_fit``
        # whenever the caller doesn't supply an explicit override —
        # ``self.width()`` / ``height()`` can lag the GL-reported
        # size on some Qt builds, leaving the centred document
        # anchored to the previous frame's dimensions.
        self._last_resize_size: tuple[int, int] = (0, 0)
        # Until the user takes manual view control (wheel-zoom or
        # explicit pan) we keep the canvas auto-fitted to the widget on
        # every resize. Otherwise the layout converging after init
        # (docks settling, tab becoming active) leaves pan / zoom stale
        # for the original size, so a click at the widget centre maps
        # to image coordinates outside the canvas — and the brush silently
        # no-ops because every dab is off-canvas.
        self._user_view_locked = False

    def _init_interaction_state(self) -> None:
        """Tool dispatch, panning, pressure, marquee animation and the drag-preview overlay."""
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
        immediately, matching raster paint apps's "open with a blank canvas"
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
            # Re-subscribe to the new empty document so wholesale
            # mutations on it (a fresh add_layer, etc.) trigger the
            # texture-upload listener.
            self._document_unsubscribe()
            self._document = PaintDocument()
            self._document_unsubscribe = self._document.listen(
                self._on_document_changed,
            )
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
        self._document_unsubscribe()
        self._document = PaintDocument()
        self._document_unsubscribe = self._document.listen(
            self._on_document_changed,
        )
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

    def set_document(self, document: PaintDocument) -> None:
        """Swap the canvas's bound :class:`PaintDocument`.

        Used by the comic-project page browser so picking a different
        page hands the canvas a different document without going
        through the load-image path. The composite cache, marquee
        animation, and texture upload are all reset because the new
        document's pixels are distinct from the previous one's.
        """
        if document is self._document:
            return
        self._document_unsubscribe()
        self._document = document
        self._document_unsubscribe = document.listen(
            self._on_document_changed,
        )
        self._marquee_segments = None
        self._marquee_timer.stop()
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        shape = document.shape
        if shape is not None:
            self.image_loaded.emit(shape[1], shape[0])
        self.update()

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

    def _on_document_changed(self) -> None:
        """Subscriber for the active PaintDocument's _notify pulses.

        Forces a full texture re-upload on the next paint and queues
        a repaint. Triggered by add / remove / move / duplicate
        layer, set_layer_attribute, merge / flatten, transform, and
        any other wholesale mutation the document signals through
        :meth:`PaintDocument.listen`.
        """
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        self.update()

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
        """Pick the most descriptive cursor available for ``tool``.

        Tool-icon QPixmaps come first (eyedropper, fill, gradient,
        bezier pen, the four selection variants, zoom) so the user
        gets a full-featured hint at a glance. Tools without a
        custom icon fall through to the per-tool ``Qt.CursorShape``
        from :data:`_TOOL_CURSORS`.
        """
        from Imervue.paint.brush_cursor import make_tool_cursor
        custom = make_tool_cursor(tool)
        if custom is not None:
            pixmap, hot_x, hot_y = custom
            self.setCursor(QCursor(pixmap, hot_x, hot_y))
            return
        self.setCursor(QCursor(cursor_for_tool(tool)))

    def set_brush_size_cursor(
        self, brush_size: int, zoom: float, *, kind: str = "brush",
    ) -> None:
        """Show a full-featured ring at the brush's screen-pixel size.

        ``brush_size`` is the brush diameter in canvas pixels;
        multiplying by ``zoom`` gives the on-screen diameter the ring
        should match. Out-of-range diameters fall back to the
        per-tool :func:`cursor_for_tool` shape — a 1-pixel brush at
        100 % zoom is unreadable as a ring, and a 1024-pixel brush
        at 4× zoom would need a 4096-pixel cursor bitmap. ``kind``
        lets the eraser get a slash-marked variant; everything else
        gets the plain brush ring.
        """
        from Imervue.paint.brush_cursor import (
            BRUSH_CURSOR_MAX_PX,
            BRUSH_CURSOR_MIN_PX,
            make_brush_cursor,
        )
        diameter = max(1, int(round(float(brush_size) * float(zoom))))
        if not BRUSH_CURSOR_MIN_PX <= diameter <= BRUSH_CURSOR_MAX_PX:
            self.setCursor(QCursor(cursor_for_tool(kind)))
            return
        pixmap, hot_x, hot_y = make_brush_cursor(
            diameter, eraser=(kind == "eraser"),
        )
        self.setCursor(QCursor(pixmap, hot_x, hot_y))

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
        # Free the outgoing texture before dropping its handle. This runs off
        # paintGL (the animation source is swapped from a signal), so it needs a
        # current GL context or the texture is orphaned on every swap — it has
        # no other free path.
        if self._onion_skin_texture is not None:
            import contextlib
            with self._current_gl_context(), contextlib.suppress(GLError):   # context already gone
                glDeleteTextures(1, [self._onion_skin_texture])
        self._onion_skin_source = callable_or_none
        self._onion_skin_texture = None   # force re-upload of new buffers
        self._onion_skin_buffer_id = None

    def _current_gl_context(self):
        """Current this widget's GL context for frees issued outside paintGL."""
        from Imervue.gpu_image_view.gl_context import make_current_guard
        return make_current_guard(self)

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

    # ---- GL lifecycle ----------------------------------------------------

    def initializeGL(self) -> None:  # pragma: no cover - GL needs display server
        glClearColor(0.12, 0.12, 0.12, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)

    def showEvent(self, event) -> None:  # pragma: no cover - Qt UI
        """Defer a fit-to-window until after Qt's first layout pass.

        The canvas is hosted inside a QTabWidget that lays out its
        pages asynchronously: the first ``resizeGL`` lands while the
        widget is still at an intermediate size (the tab bar hasn't
        finished sizing the page area), so the fit math anchors to
        that smaller dimension and the canvas ends up half off-
        screen once the layout settles.

        ``QTimer.singleShot(0, …)`` runs after Qt drains its layout
        queue; reasserting ``_fit_pending`` and forcing the next
        ``resizeGL`` / ``paintGL`` to refit catches the post-layout
        size. Cheap because the timer fires once per show.
        """
        super().showEvent(event)
        self._fit_pending = True
        QTimer.singleShot(0, self._deferred_fit_after_show)

    def _deferred_fit_after_show(self) -> None:  # pragma: no cover - Qt UI
        """Recompute the fit once Qt has finalised the widget layout."""
        widget_w, widget_h = self._last_resize_size
        if (widget_w, widget_h) == (0, 0):
            widget_w = self.width()
            widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            # Still degenerate — leave _fit_pending set so paintGL's
            # safety net retries on the next paint.
            return
        if self._user_view_locked:
            self._fit_pending = False
            return
        self._reset_view_to_fit(widget_size=(widget_w, widget_h))
        self.update()

    def resizeGL(self, w: int, h: int) -> None:  # pragma: no cover - GL
        # Qt 6 passes ``w`` / ``h`` here in DEVICE pixels (the framebuffer
        # size, computed internally as ``size() * devicePixelRatio()``).
        # We don't trust the parameter convention across Qt minor versions,
        # so the layout math reads ``self.width() / height()`` instead —
        # those are guaranteed logical pixels regardless of Qt version,
        # which keeps the fit calculation in the same coordinate space as
        # the pan / zoom values it produces. Mixing the two (treating
        # device-pixel ``h`` as if it were logical) is what previously
        # left the document anchored at the bottom of the canvas on HiDPI
        # screens — pan_y = (device_h - logical_displayed) / 2 over-shot
        # by a factor of dpr.
        log_w = max(1, int(self.width()))
        log_h = max(1, int(self.height()))
        dev_w = max(1, int(w))
        dev_h = max(1, int(h))
        glViewport(0, 0, dev_w, dev_h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Ortho stays in logical pixels so pan / zoom math draws to the
        # right region — the GL pipeline rescales to the device-pixel
        # framebuffer automatically via the viewport.
        glOrtho(0, log_w, log_h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        self._last_resize_size = (log_w, log_h)
        # Re-fit on every resize until the user manually controls the
        # view. ``_fit_pending`` covers the deferred-init case (widget
        # was too small earlier); ``_user_view_locked`` is the user-took-
        # control flag that pins the view once they wheel-zoom or pan.
        if self._fit_pending or not self._user_view_locked:
            self._reset_view_to_fit(widget_size=(log_w, log_h))

    def paintGL(self) -> None:  # pragma: no cover - GL needs display server
        if not self._gl_context_alive():
            return
        composite = self._document.composite()
        if composite is None:
            return
        self._maybe_refit_view()
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
        # ``isclose`` covers tiny accumulated drift from repeated
        # ±15° increments rather than a strict ``!= 0.0``.
        if not math.isclose(self._rotation_deg, 0.0, abs_tol=1e-6):
            glTranslatef(w / 2.0, h / 2.0, 0.0)
            glRotatef(self._rotation_deg, 0.0, 0.0, 1.0)
            glTranslatef(-w / 2.0, -h / 2.0, 0.0)

        self._draw_transparency_backdrop(w, h)
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        self._draw_overlays(w, h)
        glPopMatrix()
        # HUD overlay sits in widget-space (un-rotated) so the user
        # always sees a circular ring at the canvas centre regardless
        # of the canvas rotation. Drawn AFTER popping the modelview.
        if self._size_hud is not None:
            self._draw_size_hud()

    @staticmethod
    def _gl_context_alive() -> bool:  # pragma: no cover - GL needs display server
        """Return False (and clear safely) when no GL context is current.

        Happens on teardown when a queued paint event fires after the
        canvas was detached. Without this guard ``glClear`` returns
        ``GL_INVALID_OPERATION`` which PyOpenGL turns into a GLError
        that can take other tests down with it.
        """
        from PySide6.QtGui import QOpenGLContext
        if QOpenGLContext.currentContext() is None:
            return False
        try:
            glClear(GL_COLOR_BUFFER_BIT)
        except GLError:   # GL context torn down
            return False
        return True

    def _maybe_refit_view(self) -> None:  # pragma: no cover - GL needs display server
        """Recovery path for the deferred-fit case: re-fit when the
        widget grew between the last fit and now while the user hasn't
        taken view control. Handles the QTabWidget intermediate-size
        scenario where the first ``resizeGL`` fired before the tab
        page reached its real width.
        """
        widget_w, widget_h = self._last_resize_size
        if (widget_w, widget_h) == (0, 0):
            widget_w = self.width()
            widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            return
        needs_refit = self._fit_pending or (
            not self._user_view_locked
            and self._fitted_widget_size != (widget_w, widget_h)
        )
        if needs_refit:
            self._reset_view_to_fit(widget_size=(widget_w, widget_h))

    # ---- mouse / tablet --------------------------------------------------

    # ---- internal helpers ------------------------------------------------

    # ---- material drag-drop ---------------------------------------------


    def _upload_checker_texture(self) -> None:  # pragma: no cover - GL only
        """Build / upload the transparency-checker tile to the GPU.

        Called from ``paintGL`` the first time the canvas paints. The
        tile is tiny (``2 * _CHECKER_CELL_PX`` square) so we don't
        bother with sub-uploads — a single ``glTexImage2D`` plus the
        wrap / filter state is enough. ``GL_REPEAT`` makes the same
        tile cover the entire canvas via the texcoord scaling in
        ``paintGL``; ``GL_NEAREST`` keeps the cell edges crisp under
        any zoom.
        """
        try:
            tile = build_checker_pattern()
            tex = int(glGenTextures(1))
            glBindTexture(GL_TEXTURE_2D, tex)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA,
                tile.shape[1], tile.shape[0], 0,
                GL_RGBA, GL_UNSIGNED_BYTE, tile.tobytes(),
            )
            glBindTexture(GL_TEXTURE_2D, 0)
            self._checker_texture = tex
        except GLError:
            logger.warning("Could not upload the checker texture; using a plain backdrop",
                           exc_info=True)
            # Fallback path in paintGL renders the legacy white quad
            # if this stays None.
            self._checker_texture = None

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
