"""Tool dispatcher — routes PointerEvents to the active tool handler.

Strategy pattern. A :class:`ToolDispatcher` holds one handler instance
per tool, looks up the active tool from the shared
:class:`Imervue.paint.tool_state.ToolState` for every event, and lets
that handler mutate the canvas in place. Returning ``True`` from the
dispatcher tells :class:`Imervue.paint.canvas.PaintCanvas` to re-upload
the texture on the next paint, so canvases never repaint unnecessarily.

Each tool handler implements:

* :meth:`Tool.handle(evt, canvas) -> bool` — receive one
  :class:`PointerEvent`, mutate ``canvas`` (a numpy array) in place,
  return ``True`` if anything visible changed.

Phase 2b ships brush, eraser and eyedropper. Phase 2c-2e fill in the
remaining tools by registering more handlers in
:meth:`ToolDispatcher._build_handlers`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import numpy as np

from Imervue.paint.brush_engine import (
    round_brush_kernel,
    spacing_from_brush,
)
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
from Imervue.paint.gradient import render_gradient
from Imervue.paint.selection import (
    combine,
    magic_wand_mask,
    polygon_mask,
    rectangle_mask,
)
# Tool handlers live in the tools package; re-exported here so the
# dispatcher's ``_build_handlers`` and existing ``from tool_dispatcher import
# _CropTool`` call sites keep working unchanged.
from Imervue.paint.tools.painting import (
    BrushTool,
    EraserTool,
    EyedropperTool,
    FillTool,
)
from Imervue.paint.tools.shapes import (
    _CropTool,
    _EllipseShapeTool,
    _LineShapeTool,
    _PolygonShapeTool,
    _RectShapeTool,
)
from Imervue.paint.tools.special import (
    _BezierPenTool,
    _CloneStampTool,
    _SpeechBubbleTool,
    _TransformHandleTool,
)

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

logger = logging.getLogger("Imervue.paint.dispatcher")


# ---------------------------------------------------------------------------
# Tool protocol — every tool must implement this.
# ---------------------------------------------------------------------------


class Tool(Protocol):
    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        """Process one event. Returns ``True`` if the canvas changed."""


def _strip_alt(evt: PointerEvent, alt_bit: int) -> PointerEvent:
    """Return a copy of ``evt`` with the Alt modifier bit cleared.

    PointerEvent is a frozen-style dataclass holding plain primitives,
    so a shallow copy via ``replace`` would suffice — but the type
    isn't actually frozen. Constructing a new instance keeps the
    semantics explicit: the caller never mutates the input event.
    """
    if not (int(evt.modifiers) & alt_bit):
        return evt
    return PointerEvent(
        phase=evt.phase,
        x=evt.x, y=evt.y,
        button=evt.button,
        modifiers=int(evt.modifiers) & ~alt_bit,
        pressure=evt.pressure,
        tilt_x=evt.tilt_x,
        tilt_y=evt.tilt_y,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class ToolDispatcher:
    """Callable that routes events to the active tool handler.

    Wire it into the canvas via
    ``canvas.set_tool_dispatcher(dispatcher)``. The dispatcher reads
    :attr:`ToolState.tool` on each event so a mid-stroke tool switch
    cleanly cancels the previous handler's stroke (it never sees the
    next event, so its state is implicitly dropped).
    """

    def __init__(
        self, state: ToolState, image_provider,
        selection_provider=None, set_selection=None,
        parent_widget=None,
        reference_provider=None,
        composite_provider=None,
        panel_layout_provider=None,
        overlay_setter=None,
        commit_undo=None,
    ):
        # Damage rect from the last positively-handled event — the
        # canvas reads this after dispatch returns True so it can
        # upload only the dirty pixels via glTexSubImage2D instead of
        # full-frame glTexImage2D.
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        self._last_damage = _EMPTY_DAMAGE
        """``image_provider`` is a callable returning the live numpy
        canvas (or ``None`` if no image is loaded). ``selection_provider``
        (optional) returns the current HxW bool mask or ``None``;
        ``set_selection`` (optional) writes a new mask. ``parent_widget``
        (optional) is used as the parent for any modal tool dialogs
        (text tool, gradient tool…) so they centre on the canvas."""
        self._state = state
        self._image_provider = image_provider
        self._selection_provider = selection_provider or (lambda: None)
        self._set_selection = set_selection or (lambda mask: None)
        self._parent_widget = parent_widget
        # Returns the document's reference layer image (HxWx4 RGBA) or
        # ``None`` when no reference layer is set. Sources are wired up
        # by the workspace; tests can leave it unset and the bucket
        # falls back to sampling its own target layer.
        self._reference_provider = reference_provider or (lambda: None)
        # Returns the document's composite (every visible layer
        # flattened) for the "Sample All Layers" eyedropper. ``None``
        # falls the eyedropper back to the active-layer sample.
        self._composite_provider = composite_provider or (lambda: None)
        # Returns the active manga panel layout (or None) — the
        # snap-to-panel brush option uses this to clip strokes to
        # the panel under the cursor at press time.
        self._panel_layout_provider = panel_layout_provider or (lambda: None)
        # Sets / clears the canvas's drag-preview overlay. Tools that
        # only commit on release (rect / ellipse / line / rect select)
        # call this on press / move so the user sees what they're
        # about to commit before they let go.
        self._overlay_setter = overlay_setter or (lambda _overlay: None)
        # Called once at the end of every committed gesture so the
        # workspace can push an undo snapshot. Brushes commit on
        # release; single-click tools (fill, wand) commit on press.
        # The dispatcher figures out which boundary to fire on by
        # tracking whether a press kicked off a continuous gesture.
        self._commit_undo = commit_undo or (lambda: None)
        # Tools that span a press-move-release gesture set this on a
        # successful press; the release fires ``commit_undo``. Tools
        # that mutate on a single click commit immediately when the
        # press itself returns True.
        self._gesture_pending_commit = False
        self._handlers: dict[str, Tool] = self._build_handlers()
        self._active_tool: str | None = None
        # Holding Alt during a press redirects the event to the
        # eyedropper for the duration of the gesture. Tracks whether
        # the current ongoing stroke started with the override so the
        # follow-up move / release events stay on the eyedropper too.
        self._alt_override_active = False

    def _panel_clip_for_point(
        self, x: float, y: float,
    ) -> np.ndarray | None:
        """Return the panel-mask under ``(x, y)`` or ``None``.

        Pulled out of the BrushTool so the panel lookup logic stays
        Qt-free: BrushTool consumes a plain callable that the
        dispatcher constructs, and the dispatcher in turn consults
        :func:`Imervue.paint.manga_panels.panel_at_point`.
        """
        layout = self._panel_layout_provider()
        if layout is None:
            return None
        from Imervue.paint.manga_panels import panel_at_point, panel_mask
        index = panel_at_point(layout, x, y)
        if index is None:
            return None
        canvas = self._image_provider()
        if canvas is None:
            return None
        return panel_mask(layout, canvas.shape[:2], index)

    def __call__(self, evt: PointerEvent) -> bool:
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        canvas = self._image_provider()
        if canvas is None:
            return False
        tool_name, evt = self._resolve_tool(evt)
        if tool_name != self._active_tool and self._active_tool in self._handlers:
            # User flipped tools mid-stroke — give the old handler a
            # chance to clean up internal state if it cares.
            cancel = getattr(self._handlers[self._active_tool], "cancel", None)
            if callable(cancel):
                cancel()
        self._active_tool = tool_name
        handler = self._handlers.get(tool_name)
        if handler is None:
            return False
        try:
            handled = handler.handle(evt, canvas)
        except (ValueError, RuntimeError) as exc:
            logger.warning("tool %r raised: %s", tool_name, exc)
            return False
        # After a successful event, snapshot the tool's damage rect so
        # the canvas can do a sub-region texture upload. Tools without
        # damage tracking expose ``last_damage`` via the protocol; the
        # absence of that attribute falls through to "full upload".
        if handled:
            self._last_damage = getattr(
                handler, "last_damage", _EMPTY_DAMAGE,
            )
        else:
            self._last_damage = _EMPTY_DAMAGE
        self._maybe_commit_undo(tool_name, evt, handled)
        return handled

    # Tools whose press alone commits the gesture (no follow-up
    # release expected to mutate). Single-shot mutations.
    _SINGLE_SHOT_TOOLS = frozenset({
        "fill", "select_wand",
    })
    # Tools that mutate canvas pixels — used to gate undo snapshots
    # so a hover / hand / eyedropper interaction never burns a slot.
    _MUTATING_TOOLS = frozenset({
        "brush", "eraser", "fill", "smudge", "blur", "gradient",
        "shape_rect", "shape_ellipse", "shape_line", "shape_polygon",
        "speech_bubble", "clone_stamp",
        "select_rect", "select_lasso", "select_wand", "select_quick",
        "move",
    })

    def _maybe_commit_undo(
        self, tool_name: str | None, evt: PointerEvent, handled: bool,
    ) -> None:
        """Push an undo snapshot at the right gesture boundary.

        Continuous tools (brush, eraser, smudge, shape draws) commit
        on release/leave so a stroke counts as one undoable action.
        Single-shot tools (fill, wand) commit immediately on press.
        Tools that don't mutate pixels never commit.
        """
        if tool_name not in self._MUTATING_TOOLS:
            return
        if tool_name in self._SINGLE_SHOT_TOOLS:
            if handled and evt.phase == "press":
                self._commit_undo()
            return
        if evt.phase == "press" and handled:
            self._gesture_pending_commit = True
            return
        if evt.phase in ("release", "leave") and self._gesture_pending_commit:
            self._gesture_pending_commit = False
            self._commit_undo()

    @property
    def last_damage(self):
        """Union damage rect from the most-recent positive ``__call__``."""
        return self._last_damage

    # ---- Alt → eyedropper override --------------------------------------

    # Qt.KeyboardModifier.AltModifier.value == 0x08000000 (134217728).
    # Hard-coded here to avoid importing Qt at module-import time —
    # the dispatcher is otherwise Qt-free for unit testing.
    _ALT_MODIFIER_BIT = 0x08000000

    def _resolve_tool(
        self, evt: PointerEvent,
    ) -> tuple[str | None, PointerEvent]:
        """Return ``(tool_name, event)`` to dispatch.

        Holding Alt at press time redirects the gesture to the
        eyedropper; the subsequent move / release events on the same
        gesture stay routed there even after the modifier is released.
        Without this latch the eyedropper would only see the press
        event and the user would never receive a sampled colour
        because the pen only lifts after the modifier-up arrives.

        When the override is active the returned event has its Alt
        bit cleared — otherwise the eyedropper's own Alt convention
        ("Alt held → sample background") would fire on top of the
        modifier we used to *trigger* the eyedropper, picking the BG
        when the user just wanted the FG.
        """
        active_tool = self._state.tool
        if active_tool == "eyedropper":
            return (active_tool, evt)
        # Tools that have their own Alt convention must also bypass
        # the eyedropper override — the clone-stamp uses Alt-press
        # to set the source point, not to switch into eyedropper.
        if active_tool == "clone_stamp":
            return (active_tool, evt)
        if evt.phase == "press":
            self._alt_override_active = bool(
                int(evt.modifiers) & self._ALT_MODIFIER_BIT,
            )
        if self._alt_override_active:
            stripped = _strip_alt(evt, self._ALT_MODIFIER_BIT)
            if evt.phase in ("release", "leave"):
                # Clear after dispatching the terminating event.
                self._alt_override_active = False
            return ("eyedropper", stripped)
        return (active_tool, evt)

    # ---- internals -------------------------------------------------------

    def _build_handlers(self) -> dict[str, Tool]:
        sel_ctx = _SelectionContext(
            self._state, self._selection_provider, self._set_selection,
        )
        return {
            "brush": BrushTool(
                self._state, self._selection_provider,
                panel_clip_provider=self._panel_clip_for_point,
            ),
            "eraser": EraserTool(self._state, self._selection_provider),
            "eyedropper": EyedropperTool(
                self._state, self._composite_provider,
            ),
            "fill": FillTool(
                self._state,
                self._selection_provider,
                self._reference_provider,
            ),
            "select_rect": RectSelectTool(sel_ctx, self._overlay_setter),
            "select_lasso": LassoSelectTool(sel_ctx, self._overlay_setter),
            "select_wand": WandSelectTool(sel_ctx, self._state),
            "select_quick": QuickSelectTool(sel_ctx, self._state),
            "move": MoveTool(self._state, self._selection_provider, self._set_selection),
            "text": _build_text_tool(
                self._state, self._selection_provider, self._parent_widget,
            ),
            "gradient": GradientTool(self._state, self._selection_provider),
            "smudge": SmudgeTool(self._state, self._selection_provider),
            "blur": _BlurTool(self._state, self._selection_provider),
            "bezier_pen": _BezierPenTool(self._state, self._overlay_setter),
            "clone_stamp": _CloneStampTool(self._state, self._overlay_setter),
            "transform": _TransformHandleTool(self._state),
            "speech_bubble": _SpeechBubbleTool(self._state),
            "shape_rect": _RectShapeTool(self._state, self._overlay_setter),
            "shape_ellipse": _EllipseShapeTool(self._state, self._overlay_setter),
            "shape_line": _LineShapeTool(self._state, self._overlay_setter),
            "shape_polygon": _PolygonShapeTool(self._state, self._overlay_setter),
            "crop": _CropTool(self._state),
        }


# ---------------------------------------------------------------------------
# Selection plumbing — shared by the three selection tools.
# ---------------------------------------------------------------------------


def _build_text_tool(state, selection_provider, parent_widget):
    """Late-import the text tool so the Qt-heavy module isn't pulled in
    until the dispatcher actually constructs handlers."""
    from Imervue.paint.text_tool import TextTool
    return TextTool(state, selection_provider, parent_widget)


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


# ---------------------------------------------------------------------------
# Selection tools
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Move tool
# ---------------------------------------------------------------------------


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


class GradientTool:
    """Drag-to-define gradient using current ToolState gradient_kind."""

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._start: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._start = (evt.x, evt.y)
            return False
        if evt.phase == "release" and self._start is not None:
            start = self._start
            self._start = None
            painted = render_gradient(
                canvas, start, (evt.x, evt.y),
                fg=self._state.foreground,
                bg=self._state.background,
                kind=self._state.gradient_kind,
                reverse=self._state.gradient_reverse,
                selection=self._selection_provider(),
            )
            return painted
        return False

    def cancel(self) -> None:
        self._start = None


class SmudgeTool:
    """Drag canvas pixels along the stroke path."""

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._kernel = None
        self._carried = None
        self._spacing = 1.0
        self._last: tuple[float, float] | None = None
        self._selection_snapshot = None
        self._active = False

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            return self._begin(evt, canvas)
        if evt.phase == "move" and self._active:
            return self._extend(evt, canvas)
        if evt.phase in ("release", "leave") and self._active:
            self._extend(evt, canvas)
            self._active = False
            self._carried = None
            self._last = None
            return True
        return False

    def cancel(self) -> None:
        self._active = False
        self._carried = None
        self._last = None

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.smudge import sample_carry
        brush = self._state.brush
        self._kernel = round_brush_kernel(brush.size, brush.hardness)
        self._spacing = spacing_from_brush(brush.size, brush.hardness)
        self._selection_snapshot = self._selection_provider()
        self._carried = sample_carry(canvas, evt.x, evt.y, self._kernel)
        self._last = (evt.x, evt.y)
        self._active = True
        return False  # press alone doesn't change pixels — wait for drag

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.brush_engine import stroke_dab_positions
        from Imervue.paint.smudge import smudge_dab
        if self._last is None or self._kernel is None or self._carried is None:
            return False
        brush = self._state.brush
        # Smudge strength reuses the brush opacity slider — high opacity
        # smudges aggressively, low opacity barely shifts pigment.
        strength = max(0.05, brush.opacity)
        for px, py in stroke_dab_positions(self._last, (evt.x, evt.y), self._spacing):
            _result, self._carried = smudge_dab(
                canvas, px, py, self._kernel, self._carried,
                strength=strength,
                selection=self._selection_snapshot,
            )
        self._last = (evt.x, evt.y)
        return True


class _BlurTool:
    """Local Gaussian blur on each dab — same pointer protocol as brush."""

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._kernel = None
        self._spacing = 1.0
        self._last: tuple[float, float] | None = None
        self._selection_snapshot = None
        self._active = False
        self._damage = _EMPTY_DAMAGE

    @property
    def last_damage(self):
        return self._damage

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            return self._begin(evt, canvas)
        if evt.phase == "move" and self._active:
            return self._extend(evt, canvas)
        if evt.phase in ("release", "leave") and self._active:
            self._extend(evt, canvas)
            self._active = False
            self._last = None
            return True
        return False

    def cancel(self) -> None:
        self._active = False
        self._last = None
        self._damage = _EMPTY_DAMAGE

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.blur import blur_dab
        brush = self._state.brush
        self._kernel = round_brush_kernel(brush.size, brush.hardness)
        self._spacing = spacing_from_brush(brush.size, brush.hardness)
        self._selection_snapshot = self._selection_provider()
        self._last = (evt.x, evt.y)
        self._active = True
        rect = blur_dab(
            canvas, evt.x, evt.y, self._kernel,
            strength=max(0.05, brush.opacity),
            selection=self._selection_snapshot,
        )
        self._damage = _damage_from_rect(rect)
        return rect[2] > 0 and rect[3] > 0

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.blur import blur_dab
        from Imervue.paint.brush_engine import stroke_dab_positions
        if self._last is None or self._kernel is None:
            return False
        brush = self._state.brush
        strength = max(0.05, brush.opacity)
        union = (0, 0, 0, 0)
        for px, py in stroke_dab_positions(self._last, (evt.x, evt.y), self._spacing):
            rect = blur_dab(
                canvas, px, py, self._kernel,
                strength=strength,
                selection=self._selection_snapshot,
            )
            union = _union_rects(union, rect)
        self._last = (evt.x, evt.y)
        self._damage = _damage_from_rect(union)
        return union[2] > 0 and union[3] > 0


def _union_rects(a, b):
    if a[2] <= 0 or a[3] <= 0:
        return b
    if b[2] <= 0 or b[3] <= 0:
        return a
    x0 = min(a[0], b[0])
    y0 = min(a[1], b[1])
    x1 = max(a[0] + a[2], b[0] + b[2])
    y1 = max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def _damage_from_rect(rect):
    from Imervue.paint.damage import DamageRect
    if rect[2] <= 0 or rect[3] <= 0:
        return _EMPTY_DAMAGE
    return DamageRect(x=rect[0], y=rect[1], w=rect[2], h=rect[3])


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


