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

import numpy as np
from OpenGL.GL import glDeleteTextures
from OpenGL.error import GLError
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument
from Imervue.paint.pointer_event import PointerEvent, ToolDispatcher
from Imervue.paint.canvas_overlays import PaintCanvasOverlaysMixin, build_checker_pattern
from Imervue.paint.canvas_input import PaintCanvasInputMixin
from Imervue.paint.canvas_view import ZOOM_MAX, ZOOM_MIN, PaintCanvasViewMixin, clamp_zoom
from Imervue.paint.canvas_document import (
    DEFAULT_CANVAS_FILL,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    PaintCanvasDocumentMixin,
)
from Imervue.paint.canvas_gl import PaintCanvasGLMixin

# Other modules and the tests import these from here; the pointer event lives
# in ``pointer_event``, the checker pattern in ``canvas_overlays`` and the
# blank-canvas defaults in ``canvas_document``.
__all__ = [
    "DEFAULT_CANVAS_FILL",
    "DEFAULT_CANVAS_HEIGHT",
    "DEFAULT_CANVAS_WIDTH",
    "ZOOM_MAX",
    "ZOOM_MIN",
    "PaintCanvas",
    "PointerEvent",
    "ToolDispatcher",
    "build_checker_pattern",
    "clamp_zoom",
    "cursor_for_tool",
]


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
        PaintCanvasDocumentMixin, PaintCanvasGLMixin, QOpenGLWidget):
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
        """Tool dispatch, panning, marquee animation and the drag-preview overlay."""
        self._dispatcher: ToolDispatcher | None = None
        self._panning = False
        self._pan_anchor = (0, 0)

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
