"""Selection tools for the paint workspace.

Rect / lasso / wand / quick-select marquees, the shared selection context they
write through, the pixel translation helper and the move tool. Extracted from
``tool_dispatcher`` to keep that module within the file-length budget;
re-exported there for backwards compatibility.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.canvas import PointerEvent
from Imervue.paint.selection import (
    combine,
    magic_wand_mask,
    polygon_mask,
    rectangle_mask,
)

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class _SelectionContext:
    """Read/write helper passed to every selection tool."""

    def __init__(self, state: ToolState, provider, setter):
        self._state = state
        self._provider = provider
        self._setter = setter

    def existing(self) -> np.ndarray | None:
        return self._provider()

    def write(self, new_mask: np.ndarray) -> None:
        combined = combine(self._provider(), new_mask, self._state.selection_mode)
        self._setter(combined)

    def clear(self) -> None:
        """Drop the active selection entirely (no marquee).

        The conventional click-on-empty-area-deselects gesture: a
        rect-select press + release without movement, or any tool's
        "you didn't draw anything" branch routes through here so the
        next dab/fill/etc. operates against the full canvas instead
        of inheriting a stale empty mask.
        """
        self._setter(None)


class RectSelectTool:
    """Drag a rectangle, commit on release using the active combine mode."""

    def __init__(self, sel_ctx: _SelectionContext, overlay_setter=None):
        self._sel = sel_ctx
        self._start: tuple[int, int] | None = None
        self._overlay_setter = overlay_setter or (lambda _overlay: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._start = (int(round(evt.x)), int(round(evt.y)))
            self._overlay_setter({
                "kind": "rect",
                "x0": self._start[0], "y0": self._start[1],
                "x1": self._start[0], "y1": self._start[1],
            })
            return True
        if evt.phase == "move" and self._start is not None:
            self._overlay_setter({
                "kind": "rect",
                "x0": self._start[0], "y0": self._start[1],
                "x1": int(round(evt.x)), "y1": int(round(evt.y)),
            })
            return True
        if evt.phase == "release" and self._start is not None:
            x0, y0 = self._start
            x1, y1 = int(round(evt.x)), int(round(evt.y))
            self._start = None
            self._overlay_setter(None)
            # Click without drag → clear the selection so the user can
            # tap an empty area to deselect, the gesture every paint
            # app honours.
            if x0 == x1 and y0 == y1:
                self._sel.clear()
                return True
            h, w = canvas.shape[:2]
            mask = rectangle_mask(h, w, x0, y0, x1, y1)
            self._sel.write(mask)
            return True
        return False

    def cancel(self) -> None:
        self._start = None
        self._overlay_setter(None)


class LassoSelectTool:
    """Free-form polygon selection — close path on release."""

    def __init__(self, sel_ctx: _SelectionContext, overlay_setter=None):
        self._sel = sel_ctx
        self._points: list[tuple[float, float]] = []
        self._overlay_setter = overlay_setter or (lambda _overlay: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._points = [(evt.x, evt.y)]
            self._overlay_setter({"kind": "polyline", "points": list(self._points)})
            return True
        if evt.phase == "move" and self._points:
            self._points.append((evt.x, evt.y))
            self._overlay_setter({"kind": "polyline", "points": list(self._points)})
            return True
        if evt.phase == "release" and self._points:
            self._points.append((evt.x, evt.y))
            points = list(self._points)
            self._points = []
            self._overlay_setter(None)
            # No-drag click → clear the selection (same convention as
            # the rect-select tool's empty-rect path). "No drag"
            # means every recorded point is within a pixel of the
            # press point.
            sx, sy = points[0]
            no_drag = all(
                abs(px - sx) < 1.0 and abs(py - sy) < 1.0
                for px, py in points
            )
            if no_drag:
                self._sel.clear()
                return True
            h, w = canvas.shape[:2]
            mask = polygon_mask(h, w, points)
            self._sel.write(mask)
            return True
        return False

    def cancel(self) -> None:
        self._points = []
        self._overlay_setter(None)


class WandSelectTool:
    """Magic wand — click a pixel, select tolerance-matching neighbours."""

    def __init__(self, sel_ctx: _SelectionContext, state: ToolState):
        self._sel = sel_ctx
        self._state = state

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase != "press":
            return False
        mask = magic_wand_mask(
            canvas,
            seed_x=int(round(evt.x)),
            seed_y=int(round(evt.y)),
            tolerance=self._state.fill.tolerance,
            contiguous=self._state.fill.contiguous,
        )
        self._sel.write(mask)
        return True

    def cancel(self) -> None:
        # Quick-select is a single-shot click — there is no mid-gesture
        # state to roll back when the dispatcher cancels.
        return


class QuickSelectTool:
    """Drag-to-paint selection — accumulate wand masks under the cursor.

    Each press / move event runs a magic-wand sample at the cursor
    and unions the result into the running selection. On release,
    the accumulated mask becomes the new document selection through
    the standard ``_SelectionContext.write`` path so the active
    combine mode (replace / add / subtract / intersect) still
    applies relative to the *pre-stroke* selection.
    """

    def __init__(self, sel_ctx: _SelectionContext, state: ToolState):
        self._sel = sel_ctx
        self._state = state
        self._active = False
        # Selection accumulated since the last press — committed via
        # _sel.write when the gesture ends so the user's combine-mode
        # choice applies to the whole drag rather than each sample.
        self._accumulated: np.ndarray | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._active = True
            self._accumulated = self._wand_mask(canvas, evt)
            return True
        if evt.phase == "move" and self._active:
            sample = self._wand_mask(canvas, evt)
            if self._accumulated is None:
                self._accumulated = sample
            else:
                self._accumulated = np.logical_or(self._accumulated, sample)
            return True
        if evt.phase in ("release", "leave") and self._active:
            self._active = False
            if self._accumulated is not None and self._accumulated.any():
                self._sel.write(self._accumulated)
            self._accumulated = None
            return True
        return False

    def cancel(self) -> None:
        self._active = False
        self._accumulated = None

    def _wand_mask(
        self, canvas: np.ndarray, evt: PointerEvent,
    ) -> np.ndarray:
        return magic_wand_mask(
            canvas,
            seed_x=int(round(evt.x)),
            seed_y=int(round(evt.y)),
            tolerance=self._state.fill.tolerance,
            contiguous=self._state.fill.contiguous,
        )


def translate_selection(
    canvas: np.ndarray, selection: np.ndarray, dx: int, dy: int,
) -> np.ndarray:
    """Move the selected pixels by (dx, dy) and return the new selection.

    Pure-numpy: cuts the selected RGBA pixels (clearing the original
    location to fully-transparent) and pastes them at the offset
    location in-place. Pixels that fall off the canvas are dropped.
    Returns the translated selection mask so the caller can update its
    selection storage. This function never reads or writes outside the
    canvas bounds.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"translate_selection expects HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    if selection.shape != canvas.shape[:2]:
        raise ValueError(
            f"selection shape {selection.shape} does not match "
            f"canvas {canvas.shape[:2]}",
        )
    if dx == 0 and dy == 0:
        return selection.copy()
    h, w = canvas.shape[:2]
    cut = canvas.copy()
    canvas[selection] = (0, 0, 0, 0)

    new_selection = np.zeros_like(selection)

    src_ys, src_xs = np.nonzero(selection)
    if len(src_ys) == 0:
        return new_selection

    dst_ys = src_ys + dy
    dst_xs = src_xs + dx
    valid = (dst_ys >= 0) & (dst_ys < h) & (dst_xs >= 0) & (dst_xs < w)
    canvas[dst_ys[valid], dst_xs[valid]] = cut[src_ys[valid], src_xs[valid]]
    new_selection[dst_ys[valid], dst_xs[valid]] = True
    return new_selection


class MoveTool:
    """Drag the active selection (or the whole canvas) to a new location.

    Phase 2 ships the commit-on-release variant — the canvas is mutated
    once, on release, by the integer drag delta. Phase 3 will replace
    this with a live floating-layer preview.
    """

    def __init__(self, state: ToolState, selection_provider, set_selection):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._set_selection = set_selection or (lambda mask: None)
        self._start: tuple[int, int] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._start = (int(round(evt.x)), int(round(evt.y)))
            return False
        if evt.phase == "release" and self._start is not None:
            dx = int(round(evt.x)) - self._start[0]
            dy = int(round(evt.y)) - self._start[1]
            self._start = None
            if dx == 0 and dy == 0:
                return False
            selection = self._selection_provider()
            if selection is None:
                # No selection — move the whole canvas content.
                selection = np.ones(canvas.shape[:2], dtype=np.bool_)
            new_mask = translate_selection(canvas, selection, dx, dy)
            self._set_selection(new_mask)
            return True
        return False

    def cancel(self) -> None:
        self._start = None
