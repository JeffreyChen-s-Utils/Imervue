"""Pure colour-space conversions used by the colour dock.

Kept Qt-free so the dock's slider-driven recomputations can be unit
tested in isolation. RGB tuples are ``(0..255)`` ints; HSV tuples are
``(hue 0..360, saturation 0..1, value 0..1)``.
"""
from __future__ import annotations


def rgb_to_hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convert an ``(r, g, b)`` int tuple to ``(h, s, v)`` floats."""
    r, g, b = (max(0, min(255, int(c))) / 255.0 for c in rgb)
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin
    if delta == 0:
        hue = 0.0
    elif cmax == r:
        hue = 60.0 * (((g - b) / delta) % 6.0)
    elif cmax == g:
        hue = 60.0 * (((b - r) / delta) + 2.0)
    else:
        hue = 60.0 * (((r - g) / delta) + 4.0)
    saturation = 0.0 if cmax == 0 else delta / cmax
    value = cmax
    return (hue % 360.0, saturation, value)


def hsv_to_rgb(hsv: tuple[float, float, float]) -> tuple[int, int, int]:
    """Convert ``(h, s, v)`` to a clamped ``(r, g, b)`` int tuple."""
    h = float(hsv[0]) % 360.0
    s = max(0.0, min(1.0, float(hsv[1])))
    v = max(0.0, min(1.0, float(hsv[2])))

    c = v * s
    x = c * (1.0 - abs(((h / 60.0) % 2.0) - 1.0))
    m = v - c

    if h < 60.0:
        r1, g1, b1 = c, x, 0.0
    elif h < 120.0:
        r1, g1, b1 = x, c, 0.0
    elif h < 180.0:
        r1, g1, b1 = 0.0, c, x
    elif h < 240.0:
        r1, g1, b1 = 0.0, x, c
    elif h < 300.0:
        r1, g1, b1 = x, 0.0, c
    else:
        r1, g1, b1 = c, 0.0, x

    return (
        int(round((r1 + m) * 255.0)),
        int(round((g1 + m) * 255.0)),
        int(round((b1 + m) * 255.0)),
    )


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Return a six-digit upper-case ``#RRGGBB`` string."""
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_rgb(text: str) -> tuple[int, int, int] | None:
    """Parse ``#RRGGBB`` or ``RRGGBB`` (or 3-digit shorthand). Returns
    ``None`` if the string is not a valid hex colour.
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) != 6:
        return None
    try:
        return (
            int(cleaned[0:2], 16),
            int(cleaned[2:4], 16),
            int(cleaned[4:6], 16),
        )
    except ValueError:
        return None
