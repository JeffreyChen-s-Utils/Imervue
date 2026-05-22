"""Pure-Python edge-snap math for the desktop-pet window.

When the user releases a drag near a monitor edge, the pet window
"clicks" onto that edge so the character sits flush against the
taskbar / screen edge — matches the behaviour every commercial
desktop-pet widget has. The actual screen geometry lookup lives in
:class:`PetWindow`; this module just computes "given these numbers,
where should the window end up?" so the math is unit-testable
without a QApplication.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SNAP_THRESHOLD: int = 24
"""Pixels of distance to an edge within which the window snaps to
it. Tuned to match common Live2D widget feel — close enough that
intentional placement near the edge always docks, far enough that
"I want the pet near the edge but not touching it" still works."""


@dataclass(frozen=True)
class Rect:
    """Lightweight (x, y, w, h) rectangle — the helper compares
    window rects against screen rects so we keep both in the same
    shape and avoid importing Qt just to spell ``QRect``."""

    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass(frozen=True)
class ScreenInfo:
    """A monitor's identity + its available (work area) rectangle.

    ``name`` is whatever the platform calls the screen — Qt exposes
    it as :meth:`QScreen.name`. Useful as a stable identifier
    across sessions: same physical monitor keeps the same name even
    when the user rearranges screens or unplugs a sibling display.
    """

    name: str
    available: Rect


def resolve_screen(
    preferred_name: str, screens: list[ScreenInfo],
) -> ScreenInfo | None:
    """Pick the right :class:`ScreenInfo` for a saved
    ``preferred_name``.

    Priority:

    1. Exact name match — same physical monitor across sessions.
    2. First screen in the list — usually the primary; the caller
       passes screens in the platform's preferred order.
    3. ``None`` only when ``screens`` is empty (no displays).
    """
    if not screens:
        return None
    if preferred_name:
        for screen in screens:
            if screen.name == preferred_name:
                return screen
    return screens[0]


def clamp_window_to_screen(
    window: Rect, screen: ScreenInfo,
) -> tuple[int, int]:
    """Shift ``window`` so it sits entirely inside
    ``screen.available``, returning the new ``(x, y)``.

    Window size is preserved. When the window is *bigger* than the
    screen on an axis, that axis pins to the screen's top-left so
    the window's top-left stays visible — best the helper can do
    until the user resizes the pet."""
    avail = screen.available
    max_x = avail.right - window.w
    max_y = avail.bottom - window.h
    new_x = _clamp(window.x, avail.x, max_x)
    new_y = _clamp(window.y, avail.y, max_y)
    return new_x, new_y


def snap_to_screen_edges(
    window: Rect,
    screen: Rect,
    threshold: int = DEFAULT_SNAP_THRESHOLD,
) -> tuple[int, int]:
    """Return the snapped ``(x, y)`` for ``window`` against
    ``screen``.

    Each axis independently snaps to whichever edge (top/left or
    bottom/right) is closer **and** within ``threshold`` pixels.
    Returns the original ``(x, y)`` when neither edge is in range
    on a given axis — the pet keeps its free position then.

    The window is also clamped inside the screen on both axes so a
    drag that overshoots the edge can't strand the pet off-screen
    (a common bug in naive drag-to-move widgets when the user drags
    fast and releases past the monitor boundary).
    """
    threshold = max(threshold, 0)
    new_x = _snap_axis(window.x, window.w, screen.x, screen.w, threshold)
    new_y = _snap_axis(window.y, window.h, screen.y, screen.h, threshold)
    new_x = _clamp(new_x, screen.x, screen.right - window.w)
    new_y = _clamp(new_y, screen.y, screen.bottom - window.h)
    return new_x, new_y


def _snap_axis(
    pos: int, size: int, origin: int, span: int, threshold: int,
) -> int:
    """Snap one axis: ``pos`` is the window's top-left along the
    axis, ``size`` is the window's extent along that axis,
    ``origin`` is the screen's top-left, ``span`` is the screen's
    extent. Picks whichever edge is closer when both are in range;
    otherwise the single in-range edge; otherwise the original
    position."""
    far_pos = origin + span - size
    near_dist = abs(pos - origin)
    far_dist = abs(pos - far_pos)
    near_in_range = near_dist <= threshold
    far_in_range = far_dist <= threshold
    if near_in_range and far_in_range:
        return origin if near_dist <= far_dist else far_pos
    if near_in_range:
        return origin
    if far_in_range:
        return far_pos
    return pos


def _clamp(value: int, low: int, high: int) -> int:
    if high < low:
        # Window is bigger than the screen on this axis — clamping
        # to ``low`` keeps the top-left visible, which is the
        # best the user can do until they resize.
        return low
    if value < low:
        return low
    if value > high:
        return high
    return value


__all__ = [
    "DEFAULT_SNAP_THRESHOLD",
    "Rect",
    "ScreenInfo",
    "clamp_window_to_screen",
    "resolve_screen",
    "snap_to_screen_edges",
]
