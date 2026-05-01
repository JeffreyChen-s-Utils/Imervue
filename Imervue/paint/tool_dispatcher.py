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
    BrushStroke,
    BrushStrokeOptions,
    apply_erase_dab,
    round_brush_kernel,
    sample_pixel,
    spacing_from_brush,
)
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.fill import flood_fill
from Imervue.paint.gradient import render_gradient
from Imervue.paint.selection import (
    combine,
    magic_wand_mask,
    polygon_mask,
    rectangle_mask,
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
        self._handlers: dict[str, Tool] = self._build_handlers()
        self._active_tool: str | None = None
        # Holding Alt during a press redirects the event to the
        # eyedropper for the duration of the gesture. Tracks whether
        # the current ongoing stroke started with the override so the
        # follow-up move / release events stay on the eyedropper too.
        self._alt_override_active = False

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
        return handled

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
            "brush": BrushTool(self._state, self._selection_provider),
            "eraser": EraserTool(self._state, self._selection_provider),
            "eyedropper": EyedropperTool(self._state),
            "fill": FillTool(self._state, self._selection_provider),
            "select_rect": RectSelectTool(sel_ctx),
            "select_lasso": LassoSelectTool(sel_ctx),
            "select_wand": WandSelectTool(sel_ctx, self._state),
            "move": MoveTool(self._state, self._selection_provider, self._set_selection),
            "text": _build_text_tool(
                self._state, self._selection_provider, self._parent_widget,
            ),
            "gradient": GradientTool(self._state, self._selection_provider),
            "smudge": SmudgeTool(self._state, self._selection_provider),
            "bezier_pen": _BezierPenTool(self._state),
            "clone_stamp": _CloneStampTool(self._state),
            "transform": _TransformHandleTool(self._state),
            "speech_bubble": _SpeechBubbleTool(self._state),
            "shape_rect": _RectShapeTool(self._state),
            "shape_ellipse": _EllipseShapeTool(self._state),
            "shape_line": _LineShapeTool(self._state),
            "shape_polygon": _PolygonShapeTool(self._state),
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


# ---------------------------------------------------------------------------
# Brush tool
# ---------------------------------------------------------------------------


class BrushTool:
    """Standard brush — paints colour through the current brush kernel.

    The pipeline applied to every cursor sample is **ruler-snap →
    stabiliser → symmetry mirror**. Each stage is opt-in: an off-mode
    ruler is identity, a zero-strength stabiliser is bypassed, and an
    off-mode symmetry mirror produces a single stroke. With everything
    on, the user gets a snapped, smoothed, mirrored stroke from one
    cursor input.

    Ruler / symmetry geometry is snapshotted at press time so a
    mid-stroke mode change or canvas resize can't tear the active
    stroke.
    """

    def __init__(self, state: ToolState, selection_provider=None):
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        from Imervue.paint.rulers import Ruler
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._strokes: list[BrushStroke] = []
        self._stabilizer = None   # type: ignore[assignment]
        self._mode: str = "off"
        self._origin: tuple[float, float] = (0.0, 0.0)
        self._ruler: Ruler = Ruler()
        # Press-point of the active stroke — fed to the perspective
        # ruler so its snap line passes through where the user pressed.
        self._stroke_anchor: tuple[float, float] | None = None
        self.last_damage = _EMPTY_DAMAGE

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        if evt.phase == "press":
            self.last_damage = _EMPTY_DAMAGE
            handled = self._begin(evt, canvas)
            if handled:
                self.last_damage = self._collect_damage()
            return handled
        if evt.phase == "move" and self._strokes:
            x, y = self._snap(evt.x, evt.y)
            x, y = self._smoothed_xy(x, y)
            self._extend_all(canvas, x, y)
            self.last_damage = self._collect_damage()
            return True
        if evt.phase in ("release", "leave") and self._strokes:
            # Leaving the canvas is treated like a release so the state
            # machine never strands an active stroke.
            sx, sy = self._snap(evt.x, evt.y)
            self._drain_to(canvas, sx, sy)
            self._end_all(canvas, sx, sy)
            self.last_damage = self._collect_damage()
            self._strokes = []
            self._stabilizer = None
            self._stroke_anchor = None
            return True
        return False

    def _collect_damage(self):
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        from Imervue.paint.damage import from_dab_result
        damage = _EMPTY_DAMAGE
        for stroke in self._strokes:
            damage = damage.union(from_dab_result(stroke.stroke_damage))
        return damage

    def cancel(self) -> None:
        self._strokes = []
        self._stabilizer = None
        self._stroke_anchor = None

    def _smoothed_xy(self, x: float, y: float) -> tuple[float, float]:
        if self._stabilizer is None:
            return (x, y)
        sx, sy = self._stabilizer.step(x, y)
        # Re-snap after the stabiliser so curved-ruler interpolation is
        # pulled back onto the track. Idempotent for points already on.
        return self._snap(sx, sy)

    def _drain_to(self, canvas: np.ndarray, x: float, y: float) -> None:
        if self._stabilizer is None or not self._strokes:
            return
        for px, py in self._stabilizer.flush(x, y):
            rx, ry = self._snap(px, py)
            self._extend_all(canvas, rx, ry)

    def _snap(self, x: float, y: float) -> tuple[float, float]:
        from Imervue.paint.rulers import snap_to_ruler
        sx, sy = snap_to_ruler(
            (x, y), self._ruler, stroke_anchor=self._stroke_anchor,
        )
        if self._state.snap_to_pixel:
            from Imervue.paint.visual_guides import snap_to_pixel
            sx, sy = snap_to_pixel(sx, sy)
        return (sx, sy)

    def _mirror(self, x: float, y: float) -> list[tuple[float, float]]:
        from Imervue.paint.symmetry import mirror_points
        return mirror_points((x, y), self._mode, self._origin)

    def _extend_all(self, canvas: np.ndarray, x: float, y: float) -> None:
        for stroke, (px, py) in zip(self._strokes, self._mirror(x, y), strict=True):
            stroke.extend(canvas, px, py)

    def _end_all(self, canvas: np.ndarray, x: float, y: float) -> None:
        for stroke, (px, py) in zip(self._strokes, self._mirror(x, y), strict=True):
            stroke.end(canvas, px, py)

    # ---- internals -------------------------------------------------------

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.brush_dynamics import (
            pressure_opacity_factor,
            pressure_size_factor,
        )
        from Imervue.paint.stabilizer import StrokeStabilizer
        import time
        brush = self._state.brush
        # Stroke begins → user has committed to this colour. Record
        # it in recents now so subsequent slider tweaks don't re-bump
        # the same colour to the front.
        self._state.record_foreground_in_history()
        # Snapshot the ruler at press time, record the stroke anchor
        # for the perspective ruler, then snap the press point so
        # downstream stabiliser + mirror stages see a point on the track.
        self._ruler = self._state.ruler
        self._stroke_anchor = (float(evt.x), float(evt.y))
        sx, sy = self._snap(evt.x, evt.y)
        # Stabiliser smooths jittery input. strength=0 short-circuits the
        # filter so cheap mice with no jitter pay zero cost.
        if brush.stabilizer > 0.0:
            self._stabilizer = StrokeStabilizer(brush.stabilizer)
            self._stabilizer.begin(sx, sy)
        else:
            self._stabilizer = None
        # Pen pressure scales BOTH size and opacity — MediBang uses both
        # axes so a pen line tapers in width as well as ink density.
        size_scaled = max(1, int(round(brush.size * pressure_size_factor(evt.pressure))))
        opacity_scaled = brush.opacity * pressure_opacity_factor(evt.pressure)
        # Snapshot symmetry mode + origin at stroke start so a mid-stroke
        # mode change or canvas resize doesn't tear the mirror geometry.
        self._mode = self._state.symmetry_mode
        h, w = canvas.shape[:2]
        self._origin = (w / 2.0, h / 2.0)
        options = BrushStrokeOptions(
            color=self._state.foreground,
            size=size_scaled,
            opacity=opacity_scaled,
            hardness=brush.hardness,
            blend_mode=brush.blend_mode,
            selection=self._selection_provider(),
            kind=brush.kind,
            seed=int(time.monotonic_ns() & 0xFFFFFFFF),
            tip_path=brush.tip_path,
        )
        self._strokes = []
        for px, py in self._mirror(sx, sy):
            stroke = BrushStroke(options)
            stroke.begin(canvas, px, py)
            self._strokes.append(stroke)
        return True


# ---------------------------------------------------------------------------
# Eraser tool
# ---------------------------------------------------------------------------


class EraserTool:
    """Eraser — knocks alpha down through the current brush kernel.

    Re-implements the brush stroke loop because the rasteriser is
    designed for additive paint; the eraser path is short enough that
    re-using BrushStroke would obscure rather than help.
    """

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)
        self._kernel = None
        self._spacing = 1.0
        self._opacity = 1.0
        self._selection_snapshot: np.ndarray | None = None
        self._last: tuple[float, float] | None = None
        self._active = False

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

    def _begin(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        brush = self._state.brush
        self._kernel = round_brush_kernel(brush.size, brush.hardness)
        self._spacing = spacing_from_brush(brush.size, brush.hardness)
        pressure = max(0.1, min(1.0, evt.pressure))
        self._opacity = brush.opacity * pressure
        self._selection_snapshot = self._selection_provider()
        self._last = (evt.x, evt.y)
        self._active = True
        apply_erase_dab(
            canvas, evt.x, evt.y, self._kernel,
            opacity=self._opacity, selection=self._selection_snapshot,
        )
        return True

    def _extend(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if self._last is None or self._kernel is None:
            return False
        from Imervue.paint.brush_engine import stroke_dab_positions
        for px, py in stroke_dab_positions(self._last, (evt.x, evt.y), self._spacing):
            apply_erase_dab(
                canvas, px, py, self._kernel,
                opacity=self._opacity, selection=self._selection_snapshot,
            )
        self._last = (evt.x, evt.y)
        return True


# ---------------------------------------------------------------------------
# Eyedropper
# ---------------------------------------------------------------------------


class FillTool:
    """Paint bucket — single-click flood fills the region under the cursor."""

    def __init__(self, state: ToolState, selection_provider=None):
        self._state = state
        self._selection_provider = selection_provider or (lambda: None)

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase != "press":
            return False
        result = flood_fill(
            canvas,
            seed_x=int(round(evt.x)),
            seed_y=int(round(evt.y)),
            color=self._state.foreground,
            tolerance=self._state.fill.tolerance,
            contiguous=self._state.fill.contiguous,
            selection=self._selection_provider(),
        )
        return not result.is_empty


class EyedropperTool:
    """Click-to-pick: writes the canvas pixel under the cursor to FG.

    Move events while the button is held also update the colour so the
    user can scrub across the canvas to find the right shade — a
    MediBang convention. Modifier-aware: holding Alt picks BG instead.
    """

    ALT_MOD_VALUE: int

    def __init__(self, state: ToolState):
        self._state = state
        # Cache the alt modifier value at construction time; importing Qt
        # in this module keeps the dispatcher Qt-free at import.
        from PySide6.QtCore import Qt
        self.ALT_MOD_VALUE = int(Qt.KeyboardModifier.AltModifier.value)
        self._active = False

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._active = True
            self._sample(evt, canvas)
            return False  # canvas unchanged — only state changed
        if evt.phase == "move" and self._active:
            self._sample(evt, canvas)
            return False
        if evt.phase in ("release", "leave"):
            self._active = False
            return False
        return False

    def cancel(self) -> None:
        self._active = False

    def _sample(self, evt: PointerEvent, canvas: np.ndarray) -> None:
        pixel = sample_pixel(canvas, evt.x, evt.y)
        if pixel is None:
            return
        if evt.modifiers & self.ALT_MOD_VALUE:
            self._state.set_background(pixel)
        else:
            # Eyedropper is a deliberate "I want this colour" action,
            # so commit it to the recents history.
            self._state.set_foreground(pixel, commit=True)


# ---------------------------------------------------------------------------
# Selection tools
# ---------------------------------------------------------------------------


class RectSelectTool:
    """Drag a rectangle, commit on release using the active combine mode."""

    def __init__(self, sel_ctx: _SelectionContext):
        self._sel = sel_ctx
        self._start: tuple[int, int] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._start = (int(round(evt.x)), int(round(evt.y)))
            return False
        if evt.phase == "release" and self._start is not None:
            x0, y0 = self._start
            x1, y1 = int(round(evt.x)), int(round(evt.y))
            self._start = None
            h, w = canvas.shape[:2]
            mask = rectangle_mask(h, w, x0, y0, x1, y1)
            self._sel.write(mask)
            return True
        return False

    def cancel(self) -> None:
        self._start = None


class LassoSelectTool:
    """Free-form polygon selection — close path on release."""

    def __init__(self, sel_ctx: _SelectionContext):
        self._sel = sel_ctx
        self._points: list[tuple[float, float]] = []

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        if evt.phase == "press":
            self._points = [(evt.x, evt.y)]
            return False
        if evt.phase == "move" and self._points:
            self._points.append((evt.x, evt.y))
            return False
        if evt.phase == "release" and self._points:
            self._points.append((evt.x, evt.y))
            h, w = canvas.shape[:2]
            mask = polygon_mask(h, w, self._points)
            self._points = []
            self._sel.write(mask)
            return True
        return False

    def cancel(self) -> None:
        self._points = []


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
        pass


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

    src_ys, src_xs = np.where(selection)
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


# ---------------------------------------------------------------------------
# Bezier pen tool — append anchors to a workspace-owned BezierPath.
# ---------------------------------------------------------------------------


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

    def __init__(self, state: ToolState):
        self._state = state
        self._workspace = None   # injected lazily via the dispatcher
        self._dragging_anchor_index: int | None = None
        self._press_pos: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.bezier_path import PathNode
        path = self._workspace_path()
        if path is None:
            return False
        if evt.phase == "press":
            anchor = (float(evt.x), float(evt.y))
            path.append(PathNode(anchor=anchor))
            self._dragging_anchor_index = len(path.nodes) - 1
            self._press_pos = anchor
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
            return True
        if evt.phase in ("release", "leave"):
            self._dragging_anchor_index = None
            self._press_pos = None
            return False
        return False

    def cancel(self) -> None:
        self._dragging_anchor_index = None
        self._press_pos = None

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

    def __init__(self, state: ToolState):
        self._state = state
        from Imervue.paint.stamp_tool import StampState
        self._stamp = StampState()

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.stamp_tool import stamp_dab
        if evt.phase == "press":
            if int(evt.modifiers) & self._ALT_BIT:
                # Alt-press → set the source.
                self._stamp.set_source((evt.x, evt.y))
                return False
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


# ---------------------------------------------------------------------------
# Shape tools — rect / ellipse / line / polygon. Drag-to-define for
# the first three, multi-click for polygon (right-click closes).
# ---------------------------------------------------------------------------


def _shape_color(state: ToolState) -> tuple[int, int, int, int]:
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

    def __init__(self, state: ToolState):
        self._state = state
        self._press: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_rect
        if evt.phase == "press":
            self._press = (float(evt.x), float(evt.y))
            return False
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            self._press = None
            return rasterise_rect(
                canvas, x0, y0, float(evt.x) - x0, float(evt.y) - y0,
                _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
        return False

    def cancel(self) -> None:
        self._press = None


class _EllipseShapeTool:
    """Press → record corner; release → rasterise ellipse inscribed
    in the corner-to-corner rectangle."""

    def __init__(self, state: ToolState):
        self._state = state
        self._press: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_ellipse
        if evt.phase == "press":
            self._press = (float(evt.x), float(evt.y))
            return False
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            x1, y1 = float(evt.x), float(evt.y)
            self._press = None
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            rx = abs(x1 - x0) / 2.0
            ry = abs(y1 - y0) / 2.0
            return rasterise_ellipse(
                canvas, cx, cy, rx, ry,
                _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
        return False

    def cancel(self) -> None:
        self._press = None


class _LineShapeTool:
    """Press → record start; release → rasterise straight line."""

    def __init__(self, state: ToolState):
        self._state = state
        self._press: tuple[float, float] | None = None

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_line
        if evt.phase == "press":
            self._press = (float(evt.x), float(evt.y))
            return False
        if evt.phase == "release" and self._press is not None:
            x0, y0 = self._press
            self._press = None
            return rasterise_line(
                canvas, x0, y0, float(evt.x), float(evt.y),
                _shape_color(self._state),
                width=_shape_stroke_width(self._state),
            )
        if evt.phase in ("leave",):
            self._press = None
        return False

    def cancel(self) -> None:
        self._press = None


class _PolygonShapeTool:
    """Multi-press polygon — left-click adds a vertex, right-click or
    a click within ``CLOSE_RADIUS`` of the first vertex closes the
    polygon and rasterises it.

    The vertex list resets after every successful commit so a fresh
    polygon starts with the next press, mirroring the lasso tool's
    one-gesture-one-shape model.
    """

    CLOSE_RADIUS = 8.0
    RIGHT_BUTTON = 2   # Qt.MouseButton.RightButton.value

    def __init__(self, state: ToolState):
        self._state = state
        self._vertices: list[tuple[float, float]] = []

    def handle(self, evt: PointerEvent, canvas: np.ndarray) -> bool:
        from Imervue.paint.shape_engine import rasterise_polygon
        if evt.phase != "press":
            return False
        x, y = float(evt.x), float(evt.y)
        # Right-click commits the current vertex list as a polygon.
        if int(evt.button) == self.RIGHT_BUTTON and self._vertices:
            painted = rasterise_polygon(
                canvas, self._vertices, _shape_color(self._state),
                mode=_shape_mode(self._state),
                stroke_width=_shape_stroke_width(self._state),
            )
            self._vertices = []
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
                return painted
        # Otherwise append a new vertex; nothing painted yet.
        self._vertices.append((x, y))
        return False

    def cancel(self) -> None:
        self._vertices = []


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
            aspect = getattr(self._state, "crop_aspect", None)
            try:
                snapped = snap_to_aspect(x0, y0, evt.x, evt.y, aspect)
            except ValueError:
                snapped = (x0, y0, float(evt.x), float(evt.y))
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
