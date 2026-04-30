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

    def __call__(self, evt: PointerEvent) -> bool:
        from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
        canvas = self._image_provider()
        if canvas is None:
            return False
        tool_name = self._state.tool
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
        return snap_to_ruler(
            (x, y), self._ruler, stroke_anchor=self._stroke_anchor,
        )

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
