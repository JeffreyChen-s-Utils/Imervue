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
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from Imervue.paint.canvas import PointerEvent
from Imervue.paint.damage import EMPTY as _EMPTY_DAMAGE
# Tool handlers live in the tools package; re-exported here so the
# dispatcher's ``_build_handlers`` and existing ``from tool_dispatcher import
# _CropTool`` call sites keep working unchanged.
from Imervue.paint.tools.painting import (
    BrushTool,
    EraserTool,
    EyedropperTool,
    FillTool,
)
from Imervue.paint.tools.retouch import (
    GradientTool,
    SmudgeTool,
    _BlurTool,
    _DodgeBurnTool,
    _SpongeTool,
)
from Imervue.paint.tools.select import (
    LassoSelectTool,
    MoveTool,
    QuickSelectTool,
    RectSelectTool,
    WandSelectTool,
    _SelectionContext,
)
from Imervue.paint.tools.select import translate_selection
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

# The tool handlers live in the ``tools`` package; this module is where the
# workspace and the tests import them from.
__all__ = [
    "ToolDispatcher",
    "Tool",
    "BrushTool",
    "EraserTool",
    "EyedropperTool",
    "FillTool",
    "RectSelectTool",
    "LassoSelectTool",
    "WandSelectTool",
    "QuickSelectTool",
    "GradientTool",
    "SmudgeTool",
    "MoveTool",
    "translate_selection",
]


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


@dataclass(frozen=True)
class DispatcherHooks:
    """Optional collaborators the workspace wires into :class:`ToolDispatcher`.

    Each missing hook falls back to a no-op: ``selection_provider`` returns
    the HxW bool selection (or ``None``) and ``set_selection`` writes one;
    ``parent_widget`` parents modal tool dialogs; ``reference_provider`` and
    ``composite_provider`` return the reference layer and the flattened
    composite for sampling; ``panel_layout_provider`` returns the manga panel
    layout for snap-to-panel strokes; ``overlay_setter`` shows or clears a
    drag preview; ``commit_undo`` pushes one undo snapshot per committed gesture.
    """

    selection_provider: Callable[[], np.ndarray | None] | None = None
    set_selection: Callable[[np.ndarray | None], None] | None = None
    parent_widget: object = None
    reference_provider: Callable[[], np.ndarray | None] | None = None
    composite_provider: Callable[[], np.ndarray | None] | None = None
    panel_layout_provider: Callable[[], object] | None = None
    overlay_setter: Callable[[object], None] | None = None
    commit_undo: Callable[[], None] | None = None


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
        hooks: DispatcherHooks | None = None,
    ):
        # Damage rect from the last positively-handled event — the
        # canvas reads this after dispatch returns True so it can
        # upload only the dirty pixels via glTexSubImage2D instead of
        # full-frame glTexImage2D.
        self._last_damage = _EMPTY_DAMAGE
        """``image_provider`` is a callable returning the live numpy
        canvas (or ``None`` if no image is loaded); every optional
        collaborator comes in ``hooks`` (see :class:`DispatcherHooks`)."""
        hooks = hooks or DispatcherHooks()
        selection_provider, set_selection = hooks.selection_provider, hooks.set_selection
        parent_widget, reference_provider = hooks.parent_widget, hooks.reference_provider
        composite_provider = hooks.composite_provider
        panel_layout_provider, overlay_setter = hooks.panel_layout_provider, hooks.overlay_setter
        commit_undo = hooks.commit_undo
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
        "dodge", "burn", "sponge",
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
        # Commit a gesture that's already in flight on its release/leave even if
        # the user switched to a non-mutating tool (hand / eyedropper) mid-stroke
        # — otherwise the flag never clears and the stroke merges into the next
        # one's undo step. Checked before the mutating-tool guard for that reason.
        if evt.phase in ("release", "leave") and self._gesture_pending_commit:
            self._gesture_pending_commit = False
            self._commit_undo()
            return
        if tool_name not in self._MUTATING_TOOLS:
            return
        if tool_name in self._SINGLE_SHOT_TOOLS:
            if handled and evt.phase == "press":
                self._commit_undo()
            return
        # Arm on the first handled press OR move. Gesture tools (gradient,
        # smudge, move) return handled=False on press and only do their work
        # on the drag / release, so a press-only arm never fired — their edits
        # produced no undo snapshot and never marked the tab dirty, so the
        # work was silently discarded on close.
        if evt.phase in ("press", "move") and handled:
            self._gesture_pending_commit = True

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
            "dodge": _DodgeBurnTool(
                self._state, "dodge", self._selection_provider,
            ),
            "burn": _DodgeBurnTool(
                self._state, "burn", self._selection_provider,
            ),
            "sponge": _SpongeTool(self._state, self._selection_provider),
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


# ---------------------------------------------------------------------------
# Selection tools
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Move tool
# ---------------------------------------------------------------------------


