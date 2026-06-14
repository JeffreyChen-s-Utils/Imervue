"""Deep-zoom view navigation helpers.

Pure-Python math extracted from ``GPUImageView`` so view-transform decisions
are unit-testable without an OpenGL context.
"""
from __future__ import annotations

ACTUAL_SIZE_ZOOM = 1.0


def toggle_zoom_target(
    current_zoom: float,
    fit_zoom: float,
    *,
    actual: float = ACTUAL_SIZE_ZOOM,
    eps: float = 1e-3,
) -> float:
    """Return the zoom to switch to on a fit ↔ 100% toggle.

    At (or very near) 100% the toggle returns the fit zoom; from any other
    level it returns 100%. This mirrors the double-click behaviour common to
    image viewers.
    """
    if abs(current_zoom - actual) < eps:
        return fit_zoom
    return actual


def stepped_zoom(current: float, factor: float, lo: float, hi: float) -> float:
    """Multiply *current* zoom by *factor*, clamped to ``[lo, hi]``.

    Shared by the wheel, keyboard and pinch zoom paths so they all honour the
    same limits.
    """
    return max(lo, min(hi, current * factor))


def zoom_about_point(
    offset: float,
    cursor: float,
    old_zoom: float,
    new_zoom: float,
) -> float:
    """Return the pan offset that keeps the image point under *cursor* fixed
    while the zoom changes from *old_zoom* to *new_zoom*.

    Works on a single axis; call once per axis. ``old_zoom`` of zero is guarded
    so a degenerate state can't divide by zero.
    """
    ratio = new_zoom / old_zoom if old_zoom else 1.0
    return cursor - (cursor - offset) * ratio


def clamp_pan_offset(offset: float, image_extent: float,
                     canvas_extent: float) -> float:
    """Clamp a pan offset so the image can't be dragged off the canvas.

    Single axis: ``image_extent`` is the on-screen image size (``img_dim *
    zoom``) and ``canvas_extent`` the viewport size. When the image is smaller
    than the canvas it is re-centred; when larger, the offset is held in
    ``[canvas_extent - image_extent, 0]`` so neither edge pulls inside the view.
    """
    if image_extent <= canvas_extent:
        return (canvas_extent - image_extent) / 2
    return max(canvas_extent - image_extent, min(0.0, offset))


def reading_scroll(offset_y: float, content_h: float, view_h: float,
                   delta: float) -> tuple[float, int]:
    """Vertical reading-mode scroll with edge auto-advance.

    Returns ``(new_offset_y, advance)`` where *advance* is ``+1`` to move to the
    next image, ``-1`` to the previous, and ``0`` to stay. The image top sits at
    *offset_y* (a larger offset reveals higher content). An image shorter than
    the viewport advances on any scroll; a taller one scrolls to its edges first
    and the next scroll past an edge advances — the standard webtoon-reader flow.
    """
    if content_h <= view_h:
        if delta < 0:
            return offset_y, 1
        if delta > 0:
            return offset_y, -1
        return offset_y, 0
    min_off = view_h - content_h  # negative; bottom-aligned offset
    new_off = offset_y + delta
    if new_off > 0:
        return (offset_y, -1) if offset_y >= 0 else (0.0, 0)
    if new_off < min_off:
        return (offset_y, 1) if offset_y <= min_off else (min_off, 0)
    return new_off, 0


def zoom_to_region(
    rect: tuple[float, float, float, float],
    zoom: float,
    offset: tuple[float, float],
    canvas: tuple[float, float],
    limits: tuple[float, float],
) -> tuple[float, float, float]:
    """Zoom so the screen-space *rect* fills the canvas, returning
    ``(new_zoom, new_off_x, new_off_y)``.

    *rect* is ``(x0, y0, x1, y1)`` in widget pixels (any corner order). The
    region is mapped back to image space, scaled to fit the canvas within
    ``limits`` = ``(zoom_min, zoom_max)``, then centred. A degenerate (zero-area)
    rect is floored to one image pixel so the zoom stays finite.
    """
    off_x, off_y = offset
    canvas_w, canvas_h = canvas
    zoom_min, zoom_max = limits
    x0, x1 = sorted((rect[0], rect[2]))
    y0, y1 = sorted((rect[1], rect[3]))
    img_left = (x0 - off_x) / zoom
    img_right = (x1 - off_x) / zoom
    img_top = (y0 - off_y) / zoom
    img_bottom = (y1 - off_y) / zoom
    region_w = max(img_right - img_left, 1.0)
    region_h = max(img_bottom - img_top, 1.0)
    new_zoom = max(zoom_min, min(canvas_w / region_w, canvas_h / region_h, zoom_max))
    center_x = (img_left + img_right) / 2
    center_y = (img_top + img_bottom) / 2
    return (new_zoom,
            canvas_w / 2 - center_x * new_zoom,
            canvas_h / 2 - center_y * new_zoom)
