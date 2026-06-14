"""Pure geometry math for adapting the main window to a new screen.

When the user drags the window onto a different monitor, the window
should keep the same *relative* footprint (a window covering half the
old screen covers half the new one) and stay fully visible. All rects
are ``(x, y, w, h)`` tuples in logical pixels; the module is Qt-free so
the rescale and clamping rules are unit-testable without a QApplication
(same pattern as ``vram_budget`` / ``layers``).
"""

from __future__ import annotations

Rect = tuple[int, int, int, int]

_FULL_FRACTION = 1.0


def clamp_rect_into(rect: Rect, bounds: Rect) -> Rect:
    """Shrink *rect* to fit inside *bounds* and shift it fully on-screen."""
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    w = min(w, bw)
    h = min(h, bh)
    x = max(bx, min(x, bx + bw - w))
    y = max(by, min(y, by + bh - h))
    return x, y, w, h


def _scaled_size(window: Rect, old_screen: Rect, new_screen: Rect) -> tuple[int, int]:
    """Window size on the new screen, preserving the old relative footprint."""
    _, _, win_w, win_h = window
    _, _, old_w, old_h = old_screen
    _, _, new_w, new_h = new_screen
    frac_w = min(_FULL_FRACTION, win_w / old_w)
    frac_h = min(_FULL_FRACTION, win_h / old_h)
    return max(1, round(new_w * frac_w)), max(1, round(new_h * frac_h))


def _mapped_centre(window: Rect, old_screen: Rect, new_screen: Rect) -> tuple[float, float]:
    """Window centre mapped to the same relative position on the new screen."""
    win_x, win_y, win_w, win_h = window
    old_x, old_y, old_w, old_h = old_screen
    new_x, new_y, new_w, new_h = new_screen
    frac_x = (win_x + win_w / 2 - old_x) / old_w
    frac_y = (win_y + win_h / 2 - old_y) / old_h
    return new_x + frac_x * new_w, new_y + frac_y * new_h


def rescale_rect_between_screens(window: Rect, old_screen: Rect, new_screen: Rect) -> Rect:
    """Map *window* from *old_screen* to *new_screen*.

    Keeps the window's relative size and centre position, then clamps the
    result so the whole frame is visible on the new screen. Falls back to
    a plain clamp when *old_screen* has no usable area (unplugged or
    zero-size source screen) so the maths can't divide by zero.
    """
    if old_screen[2] <= 0 or old_screen[3] <= 0:
        return clamp_rect_into(window, new_screen)
    new_w, new_h = _scaled_size(window, old_screen, new_screen)
    centre_x, centre_y = _mapped_centre(window, old_screen, new_screen)
    target = (round(centre_x - new_w / 2), round(centre_y - new_h / 2), new_w, new_h)
    return clamp_rect_into(target, new_screen)
