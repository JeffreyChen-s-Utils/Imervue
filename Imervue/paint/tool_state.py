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
    "move",
    "text",
    "gradient",
    "blur",
    "smudge",
    "hand",
    "zoom",
)
DEFAULT_TOOL = "brush"

# Brush sub-types — the brush tool dispatches by this identifier so a single
# tool entry covers pencil / pen / marker / airbrush / watercolour without
# multiplying the toolbar.
BRUSH_KINDS = ("pencil", "pen", "marker", "airbrush", "watercolor")
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

# Brush parameter ranges — identical to MediBang's UI sliders. Settings are
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
DEFAULT_BG = (255, 255, 255)


# ---------------------------------------------------------------------------
# Listener event channels
# ---------------------------------------------------------------------------
EVENT_TOOL = "tool"            # current tool changed
EVENT_BRUSH = "brush"          # any brush setting changed
EVENT_COLOR = "color"          # foreground / background changed
EVENT_HISTORY = "history"      # color history changed


@dataclass(frozen=True)
class BrushSettings:
    """Snapshot of brush parameters; immutable so listeners can compare."""

    kind: str = DEFAULT_BRUSH_KIND
    size: int = 12
    opacity: float = 1.0
    hardness: float = 0.8
    density: float = 1.0
    blend_mode: str = DEFAULT_BLEND_MODE


@dataclass
class ToolState:
    """The mutable state container.

    Construct via :func:`load_tool_state` rather than directly so the
    ``user_setting_dict``-backed persistence and listener registry are
    wired up correctly.
    """

    tool: str = DEFAULT_TOOL
    foreground: tuple[int, int, int] = DEFAULT_FG
    background: tuple[int, int, int] = DEFAULT_BG
    brush: BrushSettings = field(default_factory=BrushSettings)
    color_history: list[tuple[int, int, int]] = field(default_factory=list)
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
        for cb in list(self._listeners):
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

    def set_foreground(self, rgb: tuple[int, int, int]) -> bool:
        rgb = _clamp_rgb(rgb)
        if rgb == self.foreground:
            return False
        self.foreground = rgb
        self._push_color_history(rgb)
        self._persist()
        self._emit(EVENT_COLOR)
        self._emit(EVENT_HISTORY)
        return True

    def set_background(self, rgb: tuple[int, int, int]) -> bool:
        rgb = _clamp_rgb(rgb)
        if rgb == self.background:
            return False
        self.background = rgb
        self._persist()
        self._emit(EVENT_COLOR)
        return True

    def swap_colors(self) -> None:
        """Exchange foreground and background — MediBang's X shortcut."""
        if self.foreground == self.background:
            return
        self.foreground, self.background = self.background, self.foreground
        self._persist()
        self._emit(EVENT_COLOR)

    def reset_colors(self) -> None:
        """Reset to black/white — MediBang's D shortcut."""
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
            "foreground": list(self.foreground),
            "background": list(self.background),
            "brush": {
                "kind": self.brush.kind,
                "size": self.brush.size,
                "opacity": self.brush.opacity,
                "hardness": self.brush.hardness,
                "density": self.brush.density,
                "blend_mode": self.brush.blend_mode,
            },
            "color_history": [list(c) for c in self.color_history],
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> ToolState:
        """Build a state from a possibly-incomplete on-disk dict."""
        raw = raw if isinstance(raw, dict) else {}
        tool = raw.get("tool")
        if tool not in TOOLS:
            tool = DEFAULT_TOOL
        fg = _safe_rgb(raw.get("foreground"), DEFAULT_FG)
        bg = _safe_rgb(raw.get("background"), DEFAULT_BG)
        brush = _brush_from_dict(raw.get("brush"))
        history = _history_from_list(raw.get("color_history"))
        return cls(
            tool=tool, foreground=fg, background=bg,
            brush=brush, color_history=history,
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


def _clamp_brush_attr(key: str, value: Any) -> Any:
    if key == "size":
        return max(BRUSH_SIZE_MIN, min(BRUSH_SIZE_MAX, int(value)))
    if key == "opacity":
        return max(BRUSH_OPACITY_MIN, min(BRUSH_OPACITY_MAX, float(value)))
    if key == "hardness":
        return max(BRUSH_HARDNESS_MIN, min(BRUSH_HARDNESS_MAX, float(value)))
    if key == "density":
        return max(BRUSH_DENSITY_MIN, min(BRUSH_DENSITY_MAX, float(value)))
    return value


def _safe_rgb(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
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
    )


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
