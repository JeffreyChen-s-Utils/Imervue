"""Pure crop geometry: aspect-ratio framing, clamping and rule-of-thirds lines.

Works in normalised ``[0, 1]`` fraction space so the results round-trip with
``Recipe.crop`` regardless of source resolution. Kept Qt-free so the framing
math is unit-testable; the crop/straighten dialog wires an aspect-preset combo
on top of it.
"""
from __future__ import annotations

# Offered in the crop UI. "free" disables aspect locking; the rest are
# "<w>:<h>" labels parsed by :func:`parse_aspect`.
ASPECT_PRESETS = (
    "free", "1:1", "4:5", "5:4", "3:2", "2:3", "16:9", "9:16",
)

_THIRD = 1.0 / 3.0


def parse_aspect(label: str) -> float | None:
    """Return the width/height ratio for a preset label, or None for 'free'.

    Unrecognised or non-positive labels also return None so a bad value just
    means "no aspect lock" rather than raising.
    """
    if not label or label == "free" or ":" not in label:
        return None
    w_str, _, h_str = label.partition(":")
    try:
        w, h = float(w_str), float(h_str)
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    return w / h


def centered_aspect_crop(image_aspect: float, ratio: float) -> tuple[float, float, float, float]:
    """Largest centred crop of *ratio* (w/h) inside an image of *image_aspect*.

    Returns ``(x, y, w, h)`` in ``[0, 1]`` fractions. A non-positive input
    collapses to the whole image (the identity crop).
    """
    if ratio <= 0 or image_aspect <= 0:
        return 0.0, 0.0, 1.0, 1.0
    if ratio >= image_aspect:
        frac_w, frac_h = 1.0, image_aspect / ratio
    else:
        frac_w, frac_h = ratio / image_aspect, 1.0
    return (1.0 - frac_w) / 2.0, (1.0 - frac_h) / 2.0, frac_w, frac_h


def clamp_crop_fraction(x: float, y: float, w: float,
                        h: float) -> tuple[float, float, float, float]:
    """Clamp a fractional crop rect into the unit square with non-negative size.

    The origin is clamped to ``[0, 1]`` first, then the extents are trimmed so
    the rect never spills past the right/bottom edge.
    """
    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    w = min(1.0 - x, max(0.0, w))
    h = min(1.0 - y, max(0.0, h))
    return x, y, w, h


def thirds_lines(x: float, y: float, w: float,
                 h: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Rule-of-thirds guide positions ``(verticals, horizontals)`` for a rect.

    Each pair is the two interior division coordinates (at 1/3 and 2/3) in the
    same space as the rect, ready for a preview overlay to draw.
    """
    verticals = (x + w * _THIRD, x + w * 2.0 * _THIRD)
    horizontals = (y + h * _THIRD, y + h * 2.0 * _THIRD)
    return verticals, horizontals
