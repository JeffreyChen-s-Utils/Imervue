"""Pure layout helpers for the deep-zoom thumbnail filmstrip.

The filmstrip is a horizontal band of neighbour thumbnails drawn at the bottom
of the deep-zoom view so the user can see the surrounding images and jump to any
of them with a click. This module holds only the Qt-free geometry — which items
are visible, where each sits, and which one a click lands on — so it is unit-
testable without a GL context. The drawing itself lives in :mod:`overlay_painter`
and the click wiring on :class:`GPUImageView`.

The band sits flush with the bottom edge; items are laid out left-to-right and
the window of visible indices is centred on the current image, clamped so it
never runs past either end of the list.
"""
from __future__ import annotations

# Per-item geometry, in logical pixels. Items are fixed cells; thumbnails are
# fitted inside them preserving aspect ratio (see :func:`fit_rect_centered`).
ITEM_WIDTH = 104
ITEM_HEIGHT = 72
ITEM_SPACING = 6
# Vertical padding above and below the thumbnails inside the band.
BAND_VPAD = 8
# Gap kept between the strip's right edge and the navigation minimap so the two
# overlays never overlap.
MINIMAP_GAP = 12


def filmstrip_band(view_height: float, item_height: float,
                   vpad: float) -> tuple[float, float]:
    """Return ``(y_top, band_height)`` for the bottom-flush filmstrip band."""
    band_height = item_height + 2 * vpad
    return view_height - band_height, band_height


def visible_filmstrip_items(current_index: int, count: int, strip_width: float,
                            item_width: float,
                            spacing: float) -> list[tuple[int, float]]:
    """Return ``(index, x_left)`` for every thumbnail to draw in the strip.

    The visible window is centred on *current_index* and clamped so it never
    extends past the list; the row is centred horizontally within *strip_width*.
    """
    if count <= 0:
        return []
    current = max(0, min(count - 1, current_index))
    step = item_width + spacing
    fit = int((strip_width + spacing) // step) if step > 0 else 1
    visible = max(1, min(fit, count))
    start = current - visible // 2
    start = max(0, min(count - visible, start))
    total_width = visible * item_width + (visible - 1) * spacing
    x0 = max(0.0, (strip_width - total_width) / 2)
    return [(start + i, x0 + i * step) for i in range(visible)]


def compute_filmstrip_items(*, enabled: bool, in_grid_mode: bool,
                            current_index: int, count: int,
                            strip_width: float) -> list[tuple[int, float]]:
    """Apply the visibility policy then lay the strip out.

    Returns an empty list (nothing to draw) when the filmstrip is disabled, the
    viewer is on the tile wall, or there is at most one image.
    """
    if not enabled or in_grid_mode or count <= 1:
        return []
    return visible_filmstrip_items(
        current_index, count, strip_width, ITEM_WIDTH, ITEM_SPACING,
    )


def filmstrip_item_at(x: float, y: float, items: list[tuple[int, float]],
                      item_width: float, y_top: float,
                      view_height: float) -> int | None:
    """Return the image index under point ``(x, y)``, or ``None`` if outside.

    *items* is the output of :func:`visible_filmstrip_items`; the click is in the
    strip when ``y`` is inside the band and ``x`` falls within an item's width.
    """
    if y < y_top or y > view_height:
        return None
    for index, x_left in items:
        if x_left <= x <= x_left + item_width:
            return index
    return None


def fit_rect_centered(content_w: float, content_h: float, box_x: float,
                      box_y: float, box_w: float,
                      box_h: float) -> tuple[float, float, float, float]:
    """Scale ``content_w`` x ``content_h`` to fit the box, preserving aspect.

    Returns the centred ``(x, y, w, h)``. A degenerate content size falls back to
    the full box so a bad thumbnail can't raise a division error.
    """
    if content_w <= 0 or content_h <= 0:
        return box_x, box_y, box_w, box_h
    scale = min(box_w / content_w, box_h / content_h)
    w = content_w * scale
    h = content_h * scale
    return box_x + (box_w - w) / 2, box_y + (box_h - h) / 2, w, h
