"""Placement maths for the hover HUD box and the loupe — pure arithmetic.

Where a HUD box fits inside the viewport, which image pixels are visible, and
which crop the loupe samples. No Qt, no GL, so the geometry is unit-testable
(project pattern: pure logic next to the Qt shell).
"""
from __future__ import annotations

from Imervue.gpu_image_view.viewport_math import visible_image_rect

# Loupe magnifier (toggle with L in deep zoom).
LOUPE_BOX_PX = 170
LOUPE_MAGNIFICATION = 4
_LOUPE_MAG_MIN = 2
_LOUPE_MAG_MAX = 16


def place_hud_box(sx: int, sy: int, size: int, box_w: int, box_h: int,
                  view_w: int, view_h: int) -> tuple[int, int]:
    """Pick a top-left for a hover HUD box that stays inside the viewport."""
    hx = sx + size + 12
    hy = sy
    if hx + box_w > view_w:
        hx = sx - box_w - 12
    if hy + box_h > view_h:
        hy = view_h - box_h - 4
    return hx, max(hy, 0)


def visible_pixel_bounds(zoom: float, off_x: float, off_y: float,
                         view_w: int, view_h: int,
                         img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Clamp the visible image-pixel rectangle to the image bounds.

    Delegates the screen->image geometry to ``viewport_math.visible_image_rect``
    and applies this HUD's integer-pixel-coverage convention (floor the top-left,
    round the bottom-right up by one).
    """
    x0, y0, x1, y1 = visible_image_rect(
        (view_w, view_h), (img_w, img_h), (off_x, off_y), zoom)
    return (
        max(0, int(x0)), max(0, int(y0)),
        min(img_w, int(x1) + 1), min(img_h, int(y1) + 1),
    )


def clamp_loupe_magnification(magnification: int, wheel_delta: float) -> int:
    """Step the loupe magnification by one on a wheel notch, clamped to range.

    A positive *wheel_delta* (scroll up) magnifies more; the result is held in
    ``[2, 16]`` so the loupe stays usable.
    """
    step = 1 if wheel_delta > 0 else -1
    return max(_LOUPE_MAG_MIN, min(_LOUPE_MAG_MAX, magnification + step))


def loupe_source_rect(img_x: int, img_y: int, sample_w: int, sample_h: int,
                      img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Image-space crop rectangle the loupe samples, centred on the cursor.

    The crop keeps its requested ``sample_w`` x ``sample_h`` size (shrinking
    only when the image itself is smaller) and is clamped so it never runs off
    the image edge, so the magnifier always shows a full square near the border.
    """
    width = min(sample_w, img_w)
    height = min(sample_h, img_h)
    left = int(round(img_x - width / 2))
    top = int(round(img_y - height / 2))
    left = max(0, min(left, img_w - width))
    top = max(0, min(top, img_h - height))
    return left, top, left + width, top + height
