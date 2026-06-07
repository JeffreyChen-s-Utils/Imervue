"""Bezier-pen, clone-stamp, transform-handle and speech-bubble tools.

Extracted from ``tool_dispatcher``; re-exported there for compatibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.canvas import PointerEvent

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class _BezierPenTool:
    """Pen-tool dispatcher — converts press events into PathNode appends.

    A press adds an anchor at the click position with no handles; a
    drag from the press through the move events extends the
    out-handle for that anchor (Photoshop convention). Release ends
    the click. The active path lives on the workspace as
    ``_bezier_pen_path`` so the user can pick up where they left off
    across multiple presses; double-click is the conventional "close
    this path" gesture but is handled at the canvas-widget level
    where Qt's QMouseEvent type carries the double-click flag.

    The tool itself doesn't rasterise — it appends nodes; once the
    user is done the workspace can call
    :func:`Imervue.paint.stroke_along_path.stroke_along_path` to
    paint the path with the active brush.
    """

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        self._workspace = None   # injected lazily via the dispatcher
        self._dragging_anchor_index: int | None = None
        self._press_pos: tuple[float, float] | None = None
        self._overlay_setter = overlay_setter or (lambda _overlay: None)

    def handle(self, evt: PointerEvent, _canvas: np.ndarray) -> bool:
        # ``_canvas`` is part of the dispatcher's tool-call contract;
        # the bezier pen mutates ``workspace._path`` instead of the
        # raster buffer so the parameter goes unused (the leading
        # underscore tells static analyzers we know).
        from Imervue.paint.bezier_path import PathNode
        path = self._workspace_path()
        if path is None:
            return False
        if evt.phase == "press":
            anchor = (float(evt.x), float(evt.y))
            path.append(PathNode(anchor=anchor))
            self._dragging_anchor_index = len(path.nodes) - 1
            self._press_pos = anchor
            self._refresh_overlay(path)
            return True
        if evt.phase == "move" and self._dragging_anchor_index is not None:
            # Mid-press drag → extend an out-handle from the anchor
            # toward the cursor; the symmetric in-handle of the next
            # node is left ``None`` until the user actually creates one.
            current = path.nodes[self._dragging_anchor_index]
            handle_out = (float(evt.x), float(evt.y))
            from dataclasses import replace
            path.replace(
                self._dragging_anchor_index,
                replace(current, handle_out=handle_out),
            )
            self._refresh_overlay(path)
            return True
        if evt.phase in ("release", "leave"):
            self._dragging_anchor_index = None
            self._press_pos = None
            return False
        return False

    def cancel(self) -> None:
        self._dragging_anchor_index = None
        self._press_pos = None
        self._overlay_setter(None)
        # Auto-commit any in-progress path so the user's clicks aren't
        # silently dropped when they switch tools — without this the
        # path stays attached to the workspace and only re-renders on
        # the next pen click, which reads as "the drawing disappeared
        # and only comes back next time I use the pen". Single-anchor
        # paths can't rasterise (``commit_pen_path`` rejects them); we
        # discard those so a fresh pen session starts clean.
        workspace = self._workspace
        if workspace is None:
            return
        path = getattr(workspace, "_bezier_pen_path", None)
        if path is None:
            return
        if len(path.nodes) >= 2:
            from Imervue.paint.pen_commit import commit_pen_path
            commit_pen_path(workspace)
        else:
            path.nodes.clear()
            path.closed = False

    def _refresh_overlay(self, path) -> None:
        """Draw the path's anchor polyline so the user sees what they
        are building before any rasterise step runs."""
        anchors = [(float(node.anchor[0]), float(node.anchor[1])) for node in path.nodes]
        if len(anchors) >= 1:
            self._overlay_setter({"kind": "polyline", "points": anchors})
        else:
            self._overlay_setter(None)

    # ---- internals ------------------------------------------------------

    def _workspace_path(self):
        """Return the workspace's active BezierPath (creating one if
        the workspace has just been opened)."""
        from Imervue.paint.bezier_path import BezierPath
        ws = self._workspace
        if ws is None:
            return None
        if not hasattr(ws, "_bezier_pen_path"):
            ws._bezier_pen_path = BezierPath()
        return ws._bezier_pen_path

    def attach_workspace(self, workspace) -> None:
        """Bind the tool to a workspace so it can read / write the
        shared :class:`BezierPath`. Called by the dispatcher when the
        workspace constructs it."""
        self._workspace = workspace


# ---------------------------------------------------------------------------
# Clone-stamp tool — wraps :mod:`stamp_tool`'s state machine.
# ---------------------------------------------------------------------------


class _CloneStampTool:
    """Clone-stamp dispatcher — Alt-press sets the source point, every
    other press / move stamps from the source area."""

    _ALT_BIT = 0x08000000   # Qt.KeyboardModifier.AltModifier.value
    _SOURCE_MARKER_RADIUS = 14.0

    def __init__(self, state: ToolState, overlay_setter=None):
        self._state = state
        from Imervue.paint.stamp_tool import StampState
        self._stamp = StampState()
        self._overlay_setter = overlay_setter or (lambda _overlay: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.stamp_tool import stamp_dab
        if evt.phase == "press":
            if int(evt.modifiers) & self._ALT_BIT:
                # Alt-press → set the source.
                self._stamp.set_source((evt.x, evt.y))
                self._update_source_overlay()
                return True
            if not self._stamp.has_source():
                # No source yet — first press without Alt does nothing
                # so the user gets a clean affordance to set source first.
                return False
            stamp_dab(
                canvas, self._stamp, evt.x, evt.y,
                size=self._state.brush.size,
                hardness=self._state.brush.hardness,
                opacity=self._state.brush.opacity,
            )
            return True
        if evt.phase == "move" and self._stamp.has_source():
            stamp_dab(
                canvas, self._stamp, evt.x, evt.y,
                size=self._state.brush.size,
                hardness=self._state.brush.hardness,
                opacity=self._state.brush.opacity,
            )
            return True
        if evt.phase in ("release", "leave"):
            self._stamp.end_stroke()
            return False
        return False

    def cancel(self) -> None:
        self._stamp.end_stroke()

    def _update_source_overlay(self) -> None:
        """Show a small ellipse at the source point so the user can
        see where the stamp will sample from."""
        if not self._stamp.has_source():
            self._overlay_setter(None)
            return
        sx, sy = self._stamp.source
        self._overlay_setter({
            "kind": "ellipse",
            "cx": float(sx), "cy": float(sy),
            "rx": float(self._SOURCE_MARKER_RADIUS),
            "ry": float(self._SOURCE_MARKER_RADIUS),
        })


# ---------------------------------------------------------------------------
# Transform handles tool — interactive scale / rotate via on-canvas handles
# ---------------------------------------------------------------------------


class _TransformHandleTool:
    """Routes pointer events through :mod:`transform_handles`.

    State lives on the workspace (``_transform_box``) so the tool can
    survive across press / move / release without being attached to
    a per-press object. The first activation sizes the box around the
    full active layer; the user then drags handles to scale / rotate.

    Commit is the responsibility of a separate workspace verb (e.g.
    pressing Enter in the canvas key handler) — this tool only
    mutates the box, never the layer pixels.
    """

    def __init__(self, state: ToolState):
        self._state = state
        self._workspace = None
        self._active_handle: str | None = None
        self._last_pos: tuple[float, float] | None = None

    def attach_workspace(self, workspace) -> None:
        self._workspace = workspace

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.transform_handles import (
            HANDLE_BODY,
            apply_handle_drag,
            from_rect,
            hit_test,
        )
        ws = self._workspace
        if ws is None:
            return False
        # Lazily seed the transform box around the layer's full extent
        # the first time the tool sees an event.
        if not hasattr(ws, "_transform_box"):
            h, w = canvas.shape[:2]
            ws._transform_box = from_rect(0.0, 0.0, float(w), float(h))
        if evt.phase == "press":
            handle = hit_test(ws._transform_box, (evt.x, evt.y))
            if handle is None:
                self._active_handle = None
                self._last_pos = None
                return False
            self._active_handle = handle if handle != HANDLE_BODY else HANDLE_BODY
            self._last_pos = (float(evt.x), float(evt.y))
            return True
        if (
            evt.phase == "move"
            and self._active_handle is not None
            and self._last_pos is not None
        ):
            delta = (
                float(evt.x) - self._last_pos[0],
                float(evt.y) - self._last_pos[1],
            )
            ws._transform_box = apply_handle_drag(
                ws._transform_box, self._active_handle, delta,
            )
            self._last_pos = (float(evt.x), float(evt.y))
            return True
        if evt.phase in ("release", "leave"):
            self._active_handle = None
            self._last_pos = None
            return False
        return False

    def cancel(self) -> None:
        self._active_handle = None
        self._last_pos = None


# ---------------------------------------------------------------------------
# Speech-bubble tool — drag-to-define ellipse + optional second click
# defines the tail tip. Press → start rect. Release → commit.
# ---------------------------------------------------------------------------


class _SpeechBubbleTool:
    """Comic-style speech bubble dispatcher.

    Two-stage gesture:

    1. **Press + drag + release** — defines the bubble's bounding rect.
       The bubble is rasterised on release with no tail.
    2. **Optional follow-up click** while the same bubble is the
       most-recently committed one — extends a tail toward the click
       point. The follow-up is recognised when the click lands within
       a small radius of the previous bubble; otherwise the tool
       starts a fresh bubble drag.

    Phase-23c ships stage 1 only — the dispatcher commits on
    release with ``tail_to=None``. A future revision can add the
    follow-up click without changing the public surface.
    """

    def __init__(self, state: ToolState):
        self._state = state
        self._press: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.speech_bubble import (
            MIN_BUBBLE_DIM,
            BubbleStyle,
            render_speech_bubble,
        )
        if evt.phase == "press":
            self._press = (float(evt.x), float(evt.y))
            return False
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            x1, y1 = float(evt.x), float(evt.y)
            self._press = None
            rx = int(round(min(x0, x1)))
            ry = int(round(min(y0, y1)))
            rw = int(round(abs(x1 - x0)))
            rh = int(round(abs(y1 - y0)))
            if rw < MIN_BUBBLE_DIM or rh < MIN_BUBBLE_DIM:
                return False
            h, w = canvas.shape[:2]
            # Clip the rect to the canvas — the user can drag beyond
            # the edge but the bubble must not write outside.
            rx = max(0, min(rx, w - MIN_BUBBLE_DIM))
            ry = max(0, min(ry, h - MIN_BUBBLE_DIM))
            rw = min(rw, w - rx)
            rh = min(rh, h - ry)
            bubble = render_speech_bubble(
                (h, w), (rx, ry, rw, rh), tail_to=None,
                style=BubbleStyle(),
            )
            # Composite the bubble onto the layer with simple
            # source-over: opaque bubble pixels overwrite the layer.
            mask = bubble[..., 3] > 0
            canvas[mask] = bubble[mask]
            return True
        if evt.phase in ("leave",):
            self._press = None
            return False
        return False

    def cancel(self) -> None:
        self._press = None


