"""Shape and crop tools for the paint workspace.

Rect / ellipse / line / polygon drag-to-define tools, the crop tool, and the
shared edge-snapping helper. Extracted from ``tool_dispatcher`` to keep that
module within the file-length budget; re-exported there for backwards
compatibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.canvas import PointerEvent

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


def _shape_color(state: ToolState) -> tuple[int, int, int, int] | None:
    """Return the shape's fill colour, or ``None`` if the foreground
    is the "transparent" slot — shape tools then no-op rather than
    deposit a phantom black fill."""
    if state.foreground is None:
        return None
    fg = tuple(int(c) for c in state.foreground)
    return (fg[0], fg[1], fg[2], 255)


def _shape_mode(state: ToolState) -> str:
    """Pull a fill / stroke mode from the workspace state, defaulting
    to ``"fill"``. Stored as ``state.shape_mode`` if the user added
    it via the options bar; absent → fill."""
    return getattr(state, "shape_mode", "fill")


def _shape_stroke_width(state: ToolState) -> int:
    """Use the brush size as the shape stroke width — keeps the
    options bar simple (one size slider drives both)."""
    return max(1, int(state.brush.size))


class _RectShapeTool:
    """Press → record corner; release → rasterise rectangle."""

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        self._press: tuple[float, float] | None = None
        self._overlay_setter = overlay_setter or (lambda _overlay: None)
        self._workspace = None

    def attach_workspace(self, workspace) -> None:
        self._workspace = workspace

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_rect
        if evt.phase == "press":
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = (sx, sy)
            self._overlay_setter({
                "kind": "rect",
                "x0": sx, "y0": sy, "x1": sx, "y1": sy,
            })
            return True
        if evt.phase == "move" and self._press is not None:
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            x0, y0 = self._press
            self._overlay_setter({
                "kind": "rect",
                "x0": x0, "y0": y0, "x1": sx, "y1": sy,
            })
            return True
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = None
            self._overlay_setter(None)
            return rasterise_rect(
                canvas, x0, y0, sx - x0, sy - y0,
                _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
            self._overlay_setter(None)
        return False

    def cancel(self) -> None:
        self._press = None
        self._overlay_setter(None)


class _EllipseShapeTool:
    """Press → record corner; release → rasterise ellipse inscribed
    in the corner-to-corner rectangle."""

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        self._press: tuple[float, float] | None = None
        self._overlay_setter = overlay_setter or (lambda _overlay: None)
        self._workspace = None

    def attach_workspace(self, workspace) -> None:
        self._workspace = workspace

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_ellipse
        if evt.phase == "press":
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = (sx, sy)
            self._overlay_setter({
                "kind": "ellipse",
                "cx": sx, "cy": sy, "rx": 0.0, "ry": 0.0,
            })
            return True
        if evt.phase == "move" and self._press is not None:
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            x0, y0 = self._press
            self._overlay_setter({
                "kind": "ellipse",
                "cx": (x0 + sx) / 2.0, "cy": (y0 + sy) / 2.0,
                "rx": abs(sx - x0) / 2.0, "ry": abs(sy - y0) / 2.0,
            })
            return True
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = None
            self._overlay_setter(None)
            cx = (x0 + sx) / 2.0
            cy = (y0 + sy) / 2.0
            rx = abs(sx - x0) / 2.0
            ry = abs(sy - y0) / 2.0
            return rasterise_ellipse(
                canvas, cx, cy, rx, ry,
                _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
            self._overlay_setter(None)
        return False

    def cancel(self) -> None:
        self._press = None
        self._overlay_setter(None)


class _LineShapeTool:
    """Press → record start; release → rasterise straight line."""

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        self._press: tuple[float, float] | None = None
        self._overlay_setter = overlay_setter or (lambda _overlay: None)
        self._workspace = None

    def attach_workspace(self, workspace) -> None:
        self._workspace = workspace

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_line
        if evt.phase == "press":
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = (sx, sy)
            self._overlay_setter({
                "kind": "line",
                "x0": sx, "y0": sy, "x1": sx, "y1": sy,
            })
            return True
        if evt.phase == "move" and self._press is not None:
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            x0, y0 = self._press
            self._overlay_setter({
                "kind": "line",
                "x0": x0, "y0": y0, "x1": sx, "y1": sy,
            })
            return True
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            sx, sy = _maybe_snap_to_edges(
                self._state, self._workspace,
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            self._press = None
            self._overlay_setter(None)
            return rasterise_line(
                canvas, x0, y0, sx, sy,
                _shape_color(self._state),
                width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
            self._overlay_setter(None)
        return False

    def cancel(self) -> None:
        self._press = None
        self._overlay_setter(None)


class _PolygonShapeTool:
    """Multi-press polygon — left-click adds a vertex, right-click or
    a click within ``CLOSE_RADIUS`` of the first vertex closes the
    polygon and rasterises it.

    The vertex list resets after every successful commit so a fresh
    polygon starts with the next press, mirroring the lasso tool's
    one-gesture-one-shape model. ``CLOSE_RADIUS`` was bumped from 8
    to 12 px because the original was too small for users to
    discover; ``move`` events now drive a live overlay so the
    in-progress polygon outline + the rubber-band line from the
    last vertex to the cursor are visible.
    """

    CLOSE_RADIUS = 12.0
    RIGHT_BUTTON = 2   # Qt.MouseButton.RightButton.value

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        self._vertices: list[tuple[float, float]] = []
        self._overlay_setter = overlay_setter or (lambda _overlay: None)
        self._cursor: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_polygon
        x, y = float(evt.x), float(evt.y)
        if evt.phase == "move":
            if self._vertices:
                self._cursor = (x, y)
                self._refresh_overlay()
                # The overlay setter triggers its own ``canvas.update()``
                # so returning ``False`` here keeps the dispatcher from
                # firing a redundant composite invalidation for an event
                # that didn't touch any layer pixels.
            return False
        if evt.phase != "press":
            return False
        # Right-click commits the current vertex list as a polygon.
        if int(evt.button) == self.RIGHT_BUTTON and self._vertices:
            painted = rasterise_polygon(
                canvas, self._vertices, _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
            self._vertices = []
            self._cursor = None
            self._overlay_setter(None)
            return painted
        # Click near the first vertex closes the polygon.
        if self._vertices:
            sx, sy = self._vertices[0]
            close_sq = (x - sx) ** 2 + (y - sy) ** 2
            if close_sq <= self.CLOSE_RADIUS * self.CLOSE_RADIUS:
                painted = rasterise_polygon(
                    canvas, self._vertices, _shape_color(self._state),
                    mode=_shape_mode(self._state),
                    stroke_width=_shape_stroke_width(self._state),
                )
                self._vertices = []
                self._cursor = None
                self._overlay_setter(None)
                return painted
        # Otherwise append a new vertex; nothing painted yet.
        self._vertices.append((x, y))
        self._cursor = (x, y)
        self._refresh_overlay()
        return False

    def _refresh_overlay(self) -> None:
        if not self._vertices:
            self._overlay_setter(None)
            return
        cursor = self._cursor
        snapping_to_close = False
        if cursor is not None and len(self._vertices) >= 2:
            sx, sy = self._vertices[0]
            close_sq = (cursor[0] - sx) ** 2 + (cursor[1] - sy) ** 2
            snapping_to_close = (
                close_sq <= self.CLOSE_RADIUS * self.CLOSE_RADIUS
            )
        # Structured polygon-preview overlay: confirmed vertices
        # rendered as solid edges, the live cursor segment, the
        # closing edge back to vertex 0, and a ring marker on
        # vertex 0 that highlights when the cursor is inside the
        # snap radius. The previous open ``polyline`` overlay made
        # in-progress polygons read like a pen-line and hid the
        # close affordance.
        self._overlay_setter({
            "kind": "polygon_preview",
            "vertices": list(self._vertices),
            "cursor": cursor,
            "snapping_to_close": snapping_to_close,
            "close_radius": self.CLOSE_RADIUS,
        })

    def cancel(self) -> None:
        self._vertices = []
        self._cursor = None
        self._overlay_setter(None)


# ---------------------------------------------------------------------------
# Crop tool — drag to define rect; commit immediately on release.
# Aspect-ratio preset (read from ``state.crop_aspect``) snaps the drag
# rectangle while it's being defined.
# ---------------------------------------------------------------------------


class _CropTool:
    """Crop dispatcher.

    Press → record one corner. Release → snap to ``state.crop_aspect``
    if set, then call ``document.crop(rect)`` via the workspace.

    The dispatcher only sees the canvas image, not the document, so
    the actual crop is delegated to ``state.canvas`` ↦ ``workspace``
    via :meth:`attach_workspace`. When no workspace is attached the
    tool is a no-op — matching the bezier pen + transform tools'
    convention.
    """

    def __init__(self, state: ToolState):
        self._state = state
        self._workspace = None
        self._press: tuple[float, float] | None = None

    def attach_workspace(self, workspace) -> None:
        self._workspace = workspace

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.crop_tool import normalise_rect, snap_to_aspect
        if evt.phase == "press":
            self._press = (float(evt.x), float(evt.y))
            return False
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            self._press = None
            # Snap the released corner to nearby edges first so the
            # aspect-ratio constraint operates on user-aligned coords.
            snapped_release = self._maybe_snap_to_edges(
                float(evt.x), float(evt.y), canvas.shape[:2],
            )
            aspect = getattr(self._state, "crop_aspect", None)
            try:
                snapped = snap_to_aspect(
                    x0, y0, snapped_release[0], snapped_release[1], aspect,
                )
            except ValueError:
                snapped = (x0, y0, snapped_release[0], snapped_release[1])
            sx0, sy0, sx1, sy1 = snapped
            rect = normalise_rect(
                sx0, sy0, sx1, sy1, canvas.shape[:2],
            )
            if rect is None:
                return False
            ws = self._workspace
            if ws is None:
                return False
            document = ws.canvas().document()
            if not document.crop(rect):
                return False
            document.invalidate_composite()
            ws.canvas().update()
            return True
        if evt.phase in ("leave",):
            self._press = None
        return False

    def cancel(self) -> None:
        self._press = None

    def _maybe_snap_to_edges(
        self, x: float, y: float, canvas_shape: tuple[int, int],
    ) -> tuple[float, float]:
        return _maybe_snap_to_edges(
            self._state, self._workspace, x, y, canvas_shape,
        )


def _maybe_snap_to_edges(
    state, workspace, x: float, y: float,
    canvas_shape: tuple[int, int],
) -> tuple[float, float]:
    """Pull ``(x, y)`` to nearby canvas / layer edges when the
    workspace state opts in via ``snap_to_edges``.

    Module-level helper so every tool that wants to participate in
    the View → Snap to Edges toggle can call it directly with a
    state + workspace pair, instead of having to subclass the crop
    tool. Returns the possibly-adjusted point; the workspace is
    optional so unit tests can call this without spinning up a
    Qt main window.
    """
    if not getattr(state, "snap_to_edges", False):
        return (x, y)
    if workspace is None:
        return (x, y)
    from Imervue.paint.snap_guides import (
        collect_canvas_candidates,
        collect_layer_candidates,
        snap_point,
    )
    try:
        x_canvas, y_canvas = collect_canvas_candidates(canvas_shape)
    except ValueError:
        return (x, y)
    document = workspace.canvas().document()
    layer_images = [
        document.layer_at(i).image for i in range(document.layer_count)
    ]
    x_layer, y_layer = collect_layer_candidates(layer_images)
    sx, sy, _hits = snap_point(
        x, y,
        x_candidates=x_canvas + x_layer,
        y_candidates=y_canvas + y_layer,
    )
    return (sx, sy)
