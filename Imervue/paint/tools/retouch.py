"""Retouch tools for the paint workspace.

Gradient fill, smudge, blur, dodge / burn and sponge — the handlers that push
pixels around instead of drawing new marks. Extracted from ``tool_dispatcher``
to keep that module within the file-length budget; re-exported there for
backwards compatibility. The dab-stroke tools (blur, dodge / burn, sponge)
live in :mod:`Imervue.paint.tools.retouch_dab` and are re-exported here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from Imervue.paint.brush_engine import round_brush_kernel, spacing_from_brush
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.gradient import render_gradient
from Imervue.paint.gradient_editor import render_multistop_gradient
from Imervue.paint.tools.retouch_dab import _BlurTool, _DodgeBurnTool, _SpongeTool

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState

__all__ = ["GradientTool", "SmudgeTool", "_BlurTool", "_DodgeBurnTool", "_SpongeTool"]


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
            return self._render(canvas, start, (evt.x, evt.y))
        return False

    def _render(self, canvas: np.ndarray, start, end) -> bool:
        """Paint the chosen saved multi-stop gradient, else foreground → background."""
        state = self._state
        shape = {"kind": state.gradient_kind, "reverse": state.gradient_reverse,
                 "repeat": state.gradient_repeat, "selection": self._selection_provider()}
        saved = _saved_gradient(state.gradient_name)
        if saved is not None:
            return render_multistop_gradient(canvas, start, end, saved, **shape)
        return render_gradient(canvas, start, end, fg=state.foreground, bg=state.background,
                               **shape)

    def cancel(self) -> None:
        self._start = None


def _saved_gradient(name: str):
    """The saved multi-stop gradient called *name*, or None (none chosen, or deleted since)."""
    if not name:
        return None
    from Imervue.paint.gradient_editor import load_gradients
    return next((g for g in load_gradients() if g.name == name), None)


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

