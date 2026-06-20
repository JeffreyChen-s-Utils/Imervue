"""Paint workspace tool state — Qt-free model.

Holds the current tool selection, foreground / background colours,
brush settings (size, opacity, hardness, density, blend mode), and a
short history of recently-used colours. Listeners (the dock panels and
the canvas) subscribe via :meth:`ToolState.subscribe` and get
notified whenever the relevant slice changes.

The full state is persisted across restarts under
``user_setting_dict["paint_state"]``. Migration is forward-only — if a
key is missing in the on-disk dict, the default kicks in. If a key is
unrecognised it is dropped silently.

This module deliberately avoids importing PySide6 so it can be
exercised in tests without a display server. The Qt panels build on
top by translating change events into widget refreshes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from Imervue.paint.rulers import Ruler
from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict

_STATE_KEY = "paint_state"

# ---------------------------------------------------------------------------
# Allowed tool identifiers. New tools added here will become available in the
# left tool bar; the canvas dispatches events by reading the current tool name.
# ---------------------------------------------------------------------------
TOOLS = (
    "brush",
    "eraser",
    "fill",
    "eyedropper",
    "select_rect",
    "select_lasso",
    "select_wand",
    "select_quick",
    "move",
    "text",
    "gradient",
    "blur",
    "smudge",
    "dodge",
    "burn",
    "hand",
    "zoom",
    "bezier_pen",
    "clone_stamp",
    "transform",
    "speech_bubble",
    "shape_rect",
    "shape_ellipse",
    "shape_line",
    "shape_polygon",
    "crop",
)
DEFAULT_TOOL = "brush"

# Brush sub-types — the brush tool dispatches by this identifier so a single
# tool entry covers pencil / pen / marker / airbrush / watercolour without
# multiplying the toolbar.
BRUSH_KINDS = ("pencil", "pen", "marker", "airbrush", "watercolor", "sumi")
DEFAULT_BRUSH_KIND = "pen"

# Blend modes the brush can paint with. Mirrors the layer blend modes the
# rest of Imervue already understands.
BLEND_MODES = (
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color_dodge",
    "color_burn",
    "soft_light",
    "hard_light",
    "linear_burn",
    "linear_dodge",
)
DEFAULT_BLEND_MODE = "normal"

# Brush parameter ranges — identical to raster paint apps's UI sliders. Settings are
# stored as plain ints/floats; clamping happens on assignment.
BRUSH_SIZE_MIN = 1
BRUSH_SIZE_MAX = 500
BRUSH_OPACITY_MIN = 0.0
BRUSH_OPACITY_MAX = 1.0
BRUSH_HARDNESS_MIN = 0.0
BRUSH_HARDNESS_MAX = 1.0
BRUSH_DENSITY_MIN = 0.0
BRUSH_DENSITY_MAX = 1.0

COLOR_HISTORY_MAX = 12
DEFAULT_FG = (0, 0, 0)
# ``None`` denotes "transparent / no colour" — the user-facing
# affordance is the swatch dock's "Transparent" button. The brush
# tool no-ops when foreground is ``None``; the gradient tool fades
# its endpoint alpha to zero. Defaulting BG to ``None`` matches the
# raster paint apps "BG slot starts empty" convention so a fresh
# ``foreground → background`` gradient produces a clean alpha fade
# without the user having to clear a stale white BG first.
DEFAULT_BG: tuple[int, int, int] | None = None
# Type alias for "either an RGB triple or transparent".
Color = "tuple[int, int, int] | None"


# ---------------------------------------------------------------------------
# Listener event channels
# ---------------------------------------------------------------------------
EVENT_TOOL = "tool"            # current tool changed
EVENT_BRUSH = "brush"          # any brush setting changed
EVENT_COLOR = "color"          # foreground / background changed
EVENT_HISTORY = "history"      # color history changed
EVENT_FILL = "fill"            # any fill setting changed
EVENT_SELECTION_MODE = "selection_mode"   # selection combine mode changed
EVENT_GRADIENT = "gradient"    # gradient kind / reverse changed
EVENT_SYMMETRY = "symmetry"    # symmetry mirror mode changed
EVENT_RULER = "ruler"          # ruler mode / geometry changed
EVENT_SUB_TOOL = "sub_tool"    # sub-tool registry / active sub-tool changed
EVENT_EYEDROPPER = "eyedropper"   # eyedropper sampling mode changed


@dataclass(frozen=True)
class BrushSettings:
    """Snapshot of brush parameters; immutable so listeners can compare."""

    kind: str = DEFAULT_BRUSH_KIND
    size: int = 12
    opacity: float = 1.0
    hardness: float = 0.8
    density: float = 1.0
    blend_mode: str = DEFAULT_BLEND_MODE
    stabilizer: float = 0.0   # 0 = off, 0..1 — input low-pass strength
    tip_path: str | None = None   # custom PNG used as kernel; None = round
    scatter: float = 0.0      # 0..1 — per-dab random offset, fraction of brush size
    color_jitter: float = 0.0 # 0..1 — per-dab HSV perturbation strength
    follow_tilt: bool = False # rotate kernel by pen tilt direction


# Fill bucket parameters live alongside brush so the dock panels and
# the dispatcher both pull from the same place.
FILL_TOLERANCE_MIN = 0
FILL_TOLERANCE_MAX = 255
# Mirrors :data:`Imervue.paint.fill.MAX_EXPAND` — duplicated as a plain
# constant so the tool-state dataclass can be imported without dragging
# in numpy / fill at module-load time.
FILL_EXPAND_MIN = 0
FILL_EXPAND_MAX = 32
FILL_GAP_CLOSE_MIN = 0
FILL_GAP_CLOSE_MAX = 16


@dataclass(frozen=True)
class FillSettings:
    """Fill bucket options."""

    tolerance: int = 32
    contiguous: bool = True
    sample_all_layers: bool = False
    expand_px: int = 0
    use_reference_layer: bool = False
    gap_close_px: int = 0


# Each entry in :attr:`ToolState.sub_tools` is a frozen snapshot of the
# brush + fill settings the user wants to recall under ``name`` for a
# given main tool. Stored under the tool id as the dict key — matching
# raster paint apps / Clip Studio's "sub-tool" tabs that hang under each main
# tool. Only the slices relevant to the tool are remembered; switching
# tools re-applies the named preset's full snapshot.
SUB_TOOL_NAME_MAX_LEN = 80


@dataclass(frozen=True)
class SubTool:
    """One saved sub-tool preset for a main tool.

    ``brush`` and ``fill`` are full settings snapshots (the same
    immutable dataclasses the live state uses) so applying a preset
    is just a swap rather than a partial diff. Sub-tools whose main
    tool doesn't use one of these slices simply ignore the unused
    field on apply.
    """

    name: str
    brush: BrushSettings = field(default_factory=BrushSettings)
    fill: FillSettings = field(default_factory=FillSettings)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("sub-tool name must be non-empty")
        if len(str(self.name)) > SUB_TOOL_NAME_MAX_LEN:
            raise ValueError(
                f"sub-tool name must be <= {SUB_TOOL_NAME_MAX_LEN} chars",
            )


@dataclass
class ToolState:
    """The mutable state container.

    Construct via :func:`load_tool_state` rather than directly so the
    ``user_setting_dict``-backed persistence and listener registry are
    wired up correctly.
    """

    tool: str = DEFAULT_TOOL
    foreground: tuple[int, int, int] | None = DEFAULT_FG
    background: tuple[int, int, int] | None = DEFAULT_BG
    brush: BrushSettings = field(default_factory=BrushSettings)
    fill: FillSettings = field(default_factory=FillSettings)
    selection_mode: str = "replace"
    gradient_kind: str = "linear"
    gradient_reverse: bool = False
    gradient_repeat: int = 1
    symmetry_mode: str = "off"
    ruler: Ruler = field(default_factory=Ruler)
    color_history: list[tuple[int, int, int]] = field(default_factory=list)
    snap_to_pixel: bool = False
    snap_to_edges: bool = False
    # When ``True`` and the workspace has a manga panel layout
    # registered, the brush clips strokes to the interior of the
    # panel containing the press point. Matches raster paint apps's
    # "コマ内描画制限" toggle. Default off so the existing brush
    # behaviour is unchanged.
    snap_to_panel: bool = False
    quick_mask_active: bool = False
    # When ``True`` the eyedropper samples from the document composite
    # (every visible layer flattened) instead of the active layer
    # only. Matches raster paint apps / PS's "Sample All Layers" eyedropper
    # toggle. False keeps the historical "active layer only" behaviour
    # so existing workflows are unchanged.
    eyedropper_sample_all_layers: bool = False
    sub_tools: dict[str, list[SubTool]] = field(default_factory=dict)
    _listeners: list[Callable[[str], None]] = field(
        default_factory=list, repr=False, compare=False,
    )

    # ---- subscribe / publish ---------------------------------------------

    def subscribe(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """Register a listener invoked with a channel name on each change.

        Returns an unsubscribe handle the caller can call to detach.
        """
        self._listeners.append(callback)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)
        return _unsubscribe

    def _emit(self, channel: str) -> None:
        for cb in self._listeners.copy():
            cb(channel)

    # ---- tool ------------------------------------------------------------

    def set_tool(self, tool: str) -> bool:
        """Switch the active tool. Returns ``True`` if it changed."""
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}; expected one of {TOOLS}")
        if tool == self.tool:
            return False
        self.tool = tool
        self._persist()
        self._emit(EVENT_TOOL)
        return True

    # ---- colours ---------------------------------------------------------

    def set_foreground(
        self,
        rgb: tuple[int, int, int] | None,
        *,
        commit: bool = False,
    ) -> bool:
        """Set the active foreground colour.

        ``rgb`` may be a 3-tuple of 0..255 ints or ``None`` to mark
        the foreground as "transparent / no colour". A transparent
        foreground turns the brush tool into a no-op (paint deposits
        nothing) so the user can pick "no colour" without first
        switching to the eraser.

        ``commit=True`` also records the colour in the recents history.
        Default is ``False`` so live-preview adjustments (slider drags,
        wheel scrolls) don't pollute "recently used" with every
        intermediate value — only colours the user actually paints
        with, picks via the colour dialog, or clicks from a swatch
        should land in recents. The transparent value is never pushed
        to history (recents are for *colours*).
        """
        rgb = _clamp_color(rgb)
        if rgb == self.foreground:
            if commit and rgb is not None:
                self._push_color_history(rgb)
                self._persist()
                self._emit(EVENT_HISTORY)
            return False
        self.foreground = rgb
        if commit and rgb is not None:
            self._push_color_history(rgb)
        self._persist()
        self._emit(EVENT_COLOR)
        if commit and rgb is not None:
            self._emit(EVENT_HISTORY)
        return True

    def record_foreground_in_history(self) -> None:
        """Push the current foreground onto the recents stack without
        otherwise changing state. Called by the brush dispatcher when
        a stroke begins so "recents" reflects colours actually used
        for paint. ``None`` (transparent) is skipped — there's no
        opaque colour to recall."""
        if self.foreground is None:
            return
        self._push_color_history(self.foreground)
        self._persist()
        self._emit(EVENT_HISTORY)

    def set_background(self, rgb: tuple[int, int, int] | None) -> bool:
        rgb = _clamp_color(rgb)
        if rgb == self.background:
            return False
        self.background = rgb
        self._persist()
        self._emit(EVENT_COLOR)
        return True

    def swap_colors(self) -> None:
        """Exchange foreground and background — raster paint apps's X shortcut."""
        if self.foreground == self.background:
            return
        self.foreground, self.background = self.background, self.foreground
        self._persist()
        self._emit(EVENT_COLOR)

    def reset_colors(self) -> None:
        """Reset to black/white — raster paint apps's D shortcut."""
        changed = False
        if self.foreground != DEFAULT_FG:
            self.foreground = DEFAULT_FG
            changed = True
        if self.background != DEFAULT_BG:
            self.background = DEFAULT_BG
            changed = True
        if changed:
            self._persist()
            self._emit(EVENT_COLOR)

    # ---- brush -----------------------------------------------------------

    def set_gradient(self, *, kind: str | None = None,
                     reverse: bool | None = None,
                     repeat: int | None = None) -> bool:
        """Update gradient kind / reverse / repeat. True if anything changed."""
        from Imervue.paint.gradient import GRADIENT_KINDS
        changed = False
        if kind is not None:
            if kind not in GRADIENT_KINDS:
                raise ValueError(
                    f"unknown gradient kind {kind!r}; expected one of {GRADIENT_KINDS}",
                )
            if kind != self.gradient_kind:
                self.gradient_kind = kind
                changed = True
        if reverse is not None and bool(reverse) != self.gradient_reverse:
            self.gradient_reverse = bool(reverse)
            changed = True
        if repeat is not None:
            repeat = max(1, int(repeat))
            if repeat != self.gradient_repeat:
                self.gradient_repeat = repeat
                changed = True
        if changed:
            self._persist()
            self._emit(EVENT_GRADIENT)
        return changed

    def set_ruler(self, ruler: Ruler | None = None, **kwargs: Any) -> bool:
        """Replace the active ruler.

        Pass either a fully-built :class:`Ruler` (``set_ruler(ruler)``) or
        keyword overrides to mutate one field at a time
        (``set_ruler(mode="linear", angle_deg=45)``); kwargs build a new
        Ruler from the current ruler with only the named fields replaced.
        Unknown modes raise ``ValueError`` so a typo can't silently fall
        back to off.
        """
        from Imervue.paint.rulers import RULER_MODES
        if ruler is None:
            ruler = replace(self.ruler, **kwargs) if kwargs else self.ruler
        elif kwargs:
            raise ValueError("set_ruler accepts either ruler= or **kwargs, not both")
        if ruler.mode not in RULER_MODES:
            raise ValueError(
                f"unknown ruler mode {ruler.mode!r}; expected one of {RULER_MODES}",
            )
        if ruler == self.ruler:
            return False
        self.ruler = ruler
        self._persist()
        self._emit(EVENT_RULER)
        return True

    def set_symmetry_mode(self, mode: str) -> bool:
        """Switch the active brush symmetry mirror mode."""
        from Imervue.paint.symmetry import SYMMETRY_MODES
        if mode not in SYMMETRY_MODES:
            raise ValueError(
                f"unknown symmetry mode {mode!r}; expected one of {SYMMETRY_MODES}",
            )
        if mode == self.symmetry_mode:
            return False
        self.symmetry_mode = mode
        self._persist()
        self._emit(EVENT_SYMMETRY)
        return True

    def set_selection_mode(self, mode: str) -> bool:
        """Switch the active selection combine mode."""
        from Imervue.paint.selection import SELECTION_MODES
        if mode not in SELECTION_MODES:
            raise ValueError(
                f"unknown selection mode {mode!r}; expected one of {SELECTION_MODES}",
            )
        if mode == self.selection_mode:
            return False
        self.selection_mode = mode
        self._persist()
        self._emit(EVENT_SELECTION_MODE)
        return True

    def set_eyedropper_sample_all_layers(self, enabled: bool) -> bool:
        """Toggle whether the eyedropper samples the composite vs active.

        Returns ``True`` if the flag changed; emits ``EVENT_EYEDROPPER``
        so listening dock panels refresh their checkbox state.
        """
        new_value = bool(enabled)
        if new_value == self.eyedropper_sample_all_layers:
            return False
        self.eyedropper_sample_all_layers = new_value
        self._persist()
        self._emit(EVENT_EYEDROPPER)
        return True

    def set_fill(self, **kwargs: Any) -> bool:
        """Update fill bucket attributes."""
        new = self.fill
        for key, value in kwargs.items():
            if not hasattr(self.fill, key):
                raise ValueError(f"unknown fill attribute {key!r}")
            new = replace(new, **{key: _clamp_fill_attr(key, value)})
        if new == self.fill:
            return False
        self.fill = new
        self._persist()
        self._emit(EVENT_FILL)
        return True

    def set_brush(self, **kwargs: Any) -> bool:
        """Update one or more brush attributes at once.

        Unknown keys are rejected to avoid silent typos. Returns ``True``
        if any attribute actually changed.
        """
        new = self.brush
        for key, value in kwargs.items():
            if not hasattr(self.brush, key):
                raise ValueError(f"unknown brush attribute {key!r}")
            new = replace(new, **{key: _clamp_brush_attr(key, value)})
        if new == self.brush:
            return False
        if new.kind not in BRUSH_KINDS:
            raise ValueError(
                f"unknown brush kind {new.kind!r}; expected one of {BRUSH_KINDS}",
            )
        if new.blend_mode not in BLEND_MODES:
            raise ValueError(
                f"unknown blend mode {new.blend_mode!r}; expected one of {BLEND_MODES}",
            )
        self.brush = new
        self._persist()
        self._emit(EVENT_BRUSH)
        return True

    # ---- sub-tools -------------------------------------------------------

    def add_sub_tool(self, tool: str, name: str) -> SubTool:
        """Capture the current brush + fill settings as a named sub-tool.

        The sub-tool is filed under ``tool`` (one of :data:`TOOLS`).
        An existing sub-tool with the same name on the same tool is
        replaced; the order of other entries is preserved. Returns
        the freshly-stored :class:`SubTool` so callers can inspect it.
        """
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}; expected one of {TOOLS}")
        sub_tool = SubTool(name=name, brush=self.brush, fill=self.fill)
        bucket = self.sub_tools.setdefault(tool, [])
        for i, existing in enumerate(bucket):
            if existing.name == sub_tool.name:
                bucket[i] = sub_tool
                self._persist()
                self._emit(EVENT_SUB_TOOL)
                return sub_tool
        bucket.append(sub_tool)
        self._persist()
        self._emit(EVENT_SUB_TOOL)
        return sub_tool

    def remove_sub_tool(self, tool: str, name: str) -> bool:
        """Drop a saved sub-tool. Returns ``True`` if it existed."""
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}; expected one of {TOOLS}")
        bucket = self.sub_tools.get(tool)
        if not bucket:
            return False
        for i, existing in enumerate(bucket):
            if existing.name == name:
                del bucket[i]
                if not bucket:
                    del self.sub_tools[tool]
                self._persist()
                self._emit(EVENT_SUB_TOOL)
                return True
        return False

    def apply_sub_tool(self, tool: str, name: str) -> bool:
        """Switch to ``tool`` and apply the named sub-tool's settings.

        Returns ``True`` if the preset was found and applied. The full
        brush and fill snapshots replace the live settings; main-tool
        switch happens before the slot writes so listeners see a
        coherent ordering of (tool change → settings change) events.
        """
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}; expected one of {TOOLS}")
        bucket = self.sub_tools.get(tool, ())
        for entry in bucket:
            if entry.name == name:
                self.set_tool(tool)
                self.brush = entry.brush
                self.fill = entry.fill
                self._persist()
                self._emit(EVENT_BRUSH)
                self._emit(EVENT_FILL)
                return True
        return False

    def list_sub_tools(self, tool: str) -> list[SubTool]:
        """Return a fresh list of sub-tools registered under ``tool``."""
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}; expected one of {TOOLS}")
        return list(self.sub_tools.get(tool, ()))

    # ---- color history ---------------------------------------------------

    def _push_color_history(self, rgb: tuple[int, int, int]) -> None:
        if rgb in self.color_history:
            self.color_history.remove(rgb)
        self.color_history.insert(0, rgb)
        del self.color_history[COLOR_HISTORY_MAX:]

    def clear_color_history(self) -> None:
        if not self.color_history:
            return
        self.color_history.clear()
        self._persist()
        self._emit(EVENT_HISTORY)

    # ---- persistence -----------------------------------------------------

    def _persist(self) -> None:
        user_setting_dict[_STATE_KEY] = self.to_dict()
        schedule_save()

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "foreground": (
                list(self.foreground) if self.foreground is not None else None
            ),
            "background": (
                list(self.background) if self.background is not None else None
            ),
            "brush": {
                "kind": self.brush.kind,
                "size": self.brush.size,
                "opacity": self.brush.opacity,
                "hardness": self.brush.hardness,
                "density": self.brush.density,
                "blend_mode": self.brush.blend_mode,
                "stabilizer": self.brush.stabilizer,
                "tip_path": self.brush.tip_path,
                "scatter": self.brush.scatter,
                "color_jitter": self.brush.color_jitter,
                "follow_tilt": self.brush.follow_tilt,
            },
            "fill": {
                "tolerance": self.fill.tolerance,
                "contiguous": self.fill.contiguous,
                "sample_all_layers": self.fill.sample_all_layers,
                "expand_px": self.fill.expand_px,
                "use_reference_layer": self.fill.use_reference_layer,
                "gap_close_px": self.fill.gap_close_px,
            },
            "selection_mode": self.selection_mode,
            "gradient_kind": self.gradient_kind,
            "gradient_reverse": self.gradient_reverse,
            "gradient_repeat": self.gradient_repeat,
            "symmetry_mode": self.symmetry_mode,
            "ruler": self.ruler.to_dict(),
            "color_history": [list(c) for c in self.color_history],
            "snap_to_pixel": bool(self.snap_to_pixel),
            "snap_to_edges": bool(self.snap_to_edges),
            "snap_to_panel": bool(self.snap_to_panel),
            "quick_mask_active": bool(self.quick_mask_active),
            "eyedropper_sample_all_layers": bool(self.eyedropper_sample_all_layers),
            "sub_tools": {
                tool: [_sub_tool_to_dict(st) for st in entries]
                for tool, entries in self.sub_tools.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> ToolState:
        """Build a state from a possibly-incomplete on-disk dict."""
        raw = raw if isinstance(raw, dict) else {}
        tool = raw.get("tool")
        if tool not in TOOLS:
            tool = DEFAULT_TOOL
        fg = _safe_color(
            raw.get("foreground", DEFAULT_FG), DEFAULT_FG,
        )
        bg = _safe_color(
            raw.get("background", DEFAULT_BG), DEFAULT_BG,
        )
        brush = _brush_from_dict(raw.get("brush"))
        fill = _fill_from_dict(raw.get("fill"))
        selection_mode = raw.get("selection_mode", "replace")
        from Imervue.paint.selection import SELECTION_MODES
        if selection_mode not in SELECTION_MODES:
            selection_mode = "replace"
        from Imervue.paint.gradient import GRADIENT_KINDS
        gradient_kind = raw.get("gradient_kind", "linear")
        if gradient_kind not in GRADIENT_KINDS:
            gradient_kind = "linear"
        gradient_reverse = bool(raw.get("gradient_reverse", False))
        try:
            gradient_repeat = max(1, int(raw.get("gradient_repeat", 1)))
        except (TypeError, ValueError):
            gradient_repeat = 1
        from Imervue.paint.symmetry import DEFAULT_SYMMETRY_MODE, SYMMETRY_MODES
        symmetry_mode = raw.get("symmetry_mode", DEFAULT_SYMMETRY_MODE)
        if symmetry_mode not in SYMMETRY_MODES:
            symmetry_mode = DEFAULT_SYMMETRY_MODE
        ruler = Ruler.from_dict(raw.get("ruler"))
        history = _history_from_list(raw.get("color_history"))
        sub_tools = _sub_tools_from_dict(raw.get("sub_tools"))
        return cls(
            tool=tool, foreground=fg, background=bg,
            brush=brush, fill=fill, selection_mode=selection_mode,
            gradient_kind=gradient_kind, gradient_reverse=gradient_reverse,
            gradient_repeat=gradient_repeat,
            symmetry_mode=symmetry_mode, ruler=ruler,
            color_history=history,
            snap_to_pixel=bool(raw.get("snap_to_pixel", False)),
            snap_to_edges=bool(raw.get("snap_to_edges", False)),
            snap_to_panel=bool(raw.get("snap_to_panel", False)),
            quick_mask_active=bool(raw.get("quick_mask_active", False)),
            eyedropper_sample_all_layers=bool(
                raw.get("eyedropper_sample_all_layers", False),
            ),
            sub_tools=sub_tools,
        )


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_INSTANCE: ToolState | None = None


def load_tool_state() -> ToolState:
    """Return (and lazily build) the process-wide ``ToolState`` singleton."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ToolState.from_dict(user_setting_dict.get(_STATE_KEY))
    return _INSTANCE


def reset_tool_state() -> None:
    """Drop the cached singleton — used by tests to force re-load."""
    global _INSTANCE
    _INSTANCE = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        raise ValueError(f"rgb must be a 3-tuple, got {rgb!r}")
    return tuple(max(0, min(255, int(c))) for c in rgb)  # type: ignore[return-value]


def _clamp_color(
    color: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    """Like :func:`_clamp_rgb` but lets ``None`` pass through unchanged.

    The setters use this so callers can pass ``None`` to mean
    "transparent" without raising on the 3-tuple check.
    """
    if color is None:
        return None
    return _clamp_rgb(color)


def _clamp_fill_attr(key: str, value: Any) -> Any:
    if key == "tolerance":
        return max(FILL_TOLERANCE_MIN, min(FILL_TOLERANCE_MAX, int(value)))
    if key == "expand_px":
        return max(FILL_EXPAND_MIN, min(FILL_EXPAND_MAX, int(value)))
    if key == "gap_close_px":
        return max(FILL_GAP_CLOSE_MIN, min(FILL_GAP_CLOSE_MAX, int(value)))
    if key in ("contiguous", "sample_all_layers", "use_reference_layer"):
        return bool(value)
    return value


def _fill_from_dict(raw: Any) -> FillSettings:
    if not isinstance(raw, dict):
        return FillSettings()
    return FillSettings(
        tolerance=_clamp_fill_attr("tolerance", raw.get("tolerance", 32)),
        contiguous=bool(raw.get("contiguous", True)),
        sample_all_layers=bool(raw.get("sample_all_layers", False)),
        expand_px=_clamp_fill_attr("expand_px", raw.get("expand_px", 0)),
        use_reference_layer=bool(raw.get("use_reference_layer", False)),
        gap_close_px=_clamp_fill_attr("gap_close_px", raw.get("gap_close_px", 0)),
    )


def _clamp_brush_attr(key: str, value: Any) -> Any:
    if key == "size":
        return max(BRUSH_SIZE_MIN, min(BRUSH_SIZE_MAX, int(value)))
    if key == "opacity":
        return max(BRUSH_OPACITY_MIN, min(BRUSH_OPACITY_MAX, float(value)))
    if key == "hardness":
        return max(BRUSH_HARDNESS_MIN, min(BRUSH_HARDNESS_MAX, float(value)))
    if key == "density":
        return max(BRUSH_DENSITY_MIN, min(BRUSH_DENSITY_MAX, float(value)))
    if key == "stabilizer":
        return max(0.0, min(1.0, float(value)))
    if key in ("scatter", "color_jitter"):
        return max(0.0, min(1.0, float(value)))
    if key == "follow_tilt":
        return bool(value)
    if key == "tip_path":
        if value is None:
            return None
        return str(value) if value else None
    return value


def _safe_rgb(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return _clamp_rgb(tuple(int(c) for c in value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return default


def _safe_color(
    value: Any,
    default: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    """Same as :func:`_safe_rgb` but ``None`` round-trips through the
    on-disk JSON representation.

    Stored as ``null`` in the user-settings dict; reading back ``None``
    or a missing key both yield the supplied ``default`` (which itself
    may be ``None``). Anything else is forwarded to ``_safe_rgb``.
    """
    if value is None:
        return default if default is None else _clamp_rgb(default)
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return _clamp_rgb(tuple(int(c) for c in value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return default


def _brush_from_dict(raw: Any) -> BrushSettings:
    if not isinstance(raw, dict):
        return BrushSettings()
    kind = raw.get("kind")
    if kind not in BRUSH_KINDS:
        kind = DEFAULT_BRUSH_KIND
    blend = raw.get("blend_mode")
    if blend not in BLEND_MODES:
        blend = DEFAULT_BLEND_MODE
    return BrushSettings(
        kind=kind,
        size=_clamp_brush_attr("size", raw.get("size", 12)),
        opacity=_clamp_brush_attr("opacity", raw.get("opacity", 1.0)),
        hardness=_clamp_brush_attr("hardness", raw.get("hardness", 0.8)),
        density=_clamp_brush_attr("density", raw.get("density", 1.0)),
        blend_mode=blend,
        stabilizer=_clamp_brush_attr("stabilizer", raw.get("stabilizer", 0.0)),
        tip_path=_clamp_brush_attr("tip_path", raw.get("tip_path")),
        scatter=_clamp_brush_attr("scatter", raw.get("scatter", 0.0)),
        color_jitter=_clamp_brush_attr("color_jitter", raw.get("color_jitter", 0.0)),
        follow_tilt=_clamp_brush_attr("follow_tilt", raw.get("follow_tilt", False)),
    )


def _sub_tool_to_dict(sub_tool: SubTool) -> dict:
    return {
        "name": str(sub_tool.name),
        "brush": {
            "kind": sub_tool.brush.kind,
            "size": sub_tool.brush.size,
            "opacity": sub_tool.brush.opacity,
            "hardness": sub_tool.brush.hardness,
            "density": sub_tool.brush.density,
            "blend_mode": sub_tool.brush.blend_mode,
            "stabilizer": sub_tool.brush.stabilizer,
            "tip_path": sub_tool.brush.tip_path,
            "scatter": sub_tool.brush.scatter,
            "color_jitter": sub_tool.brush.color_jitter,
            "follow_tilt": sub_tool.brush.follow_tilt,
        },
        "fill": {
            "tolerance": sub_tool.fill.tolerance,
            "contiguous": sub_tool.fill.contiguous,
            "sample_all_layers": sub_tool.fill.sample_all_layers,
            "expand_px": sub_tool.fill.expand_px,
            "use_reference_layer": sub_tool.fill.use_reference_layer,
        },
    }


def _sub_tools_from_dict(raw: Any) -> dict[str, list[SubTool]]:
    """Re-hydrate a saved ``sub_tools`` dict, dropping malformed entries."""
    out: dict[str, list[SubTool]] = {}
    if not isinstance(raw, dict):
        return out
    for tool, entries in raw.items():
        if tool not in TOOLS or not isinstance(entries, list):
            continue
        bucket: list[SubTool] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                bucket.append(SubTool(
                    name=str(entry.get("name", "")),
                    brush=_brush_from_dict(entry.get("brush")),
                    fill=_fill_from_dict(entry.get("fill")),
                ))
            except (TypeError, ValueError):
                continue
        if bucket:
            out[tool] = bucket
    return out


def _history_from_list(raw: Any) -> list[tuple[int, int, int]]:
    if not isinstance(raw, list):
        return []
    out: list[tuple[int, int, int]] = []
    for entry in raw:
        if isinstance(entry, (list, tuple)) and len(entry) == 3:
            try:
                out.append(_clamp_rgb(tuple(int(c) for c in entry)))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
        if len(out) >= COLOR_HISTORY_MAX:
            break
    return out
