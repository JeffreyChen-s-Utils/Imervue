"""Fit-to-window / width / height zoom + centring for :class:`GPUImageView`.

Computes the zoom and deep-zoom offsets that fit the current image to the
canvas. Reads the most-recent ``resizeGL`` size when available (it's
authoritative for the GL coordinate system and avoids the brief frames
where ``view.width()`` lags the actual layout).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.gpu_image_view.filmstrip import BAND_VPAD, ITEM_HEIGHT
from Imervue.gpu_image_view.minimap import MINIMAP_MARGIN, minimap_geometry

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_MAX_FIT_ZOOM = 1.0
# Slack on the "whole image visible" test so a zoom a hair above the full-canvas
# fit (rounding) still counts as a whole-image view to re-fit, not a zoom-in.
_FIT_EPSILON = 1.001


def canvas_size(view: GPUImageView) -> tuple[int, int]:
    """Return the logical canvas size, preferring the last resizeGL size.

    Single source of truth for "how big is the drawing surface". The
    deep-zoom renderer reads the SAME helper so the centring offsets computed
    here are mapped to screen against the identical size — otherwise the image
    lands off-centre during the brief frames where ``view.width()`` lags the
    real layout (the "Home key shifts x/y" bug).
    """
    if view._last_resize_size != (0, 0):
        return view._last_resize_size
    return view.width() or 1, view.height() or 1


def _base_dimensions(view: GPUImageView) -> tuple[int, int]:
    base = view.deep_zoom.levels[0]
    return base.shape[1], base.shape[0]


def _filmstrip_overlaps(view: GPUImageView) -> bool:
    """True when the bottom filmstrip band is being drawn over the image."""
    model = getattr(view, "model", None)
    images = getattr(model, "images", ()) if model is not None else ()
    return bool(getattr(view, "_filmstrip_enabled", False) and len(images) > 1)


def reserved_overlay_height(view: GPUImageView) -> int:
    """Bottom band (logical px) kept clear of image pixels in deep zoom.

    The minimap is always drawn and the filmstrip optionally, both flush with
    the bottom edge; reserving the taller of the two lets the fit / centring /
    pan-clamp math letterbox the image above them instead of under them. Zero
    outside deep zoom — the tile wall reserves nothing.
    """
    if not view.deep_zoom or getattr(view, "tile_grid_mode", False):
        return 0
    img_w, img_h = _base_dimensions(view)
    canvas_w, canvas_h = canvas_size(view)
    _, _, _, minimap_h = minimap_geometry(canvas_w, canvas_h, img_w, img_h)
    reserved = minimap_h + MINIMAP_MARGIN
    if _filmstrip_overlaps(view):
        reserved = max(reserved, ITEM_HEIGHT + 2 * BAND_VPAD)
    return int(reserved)


def content_size(view: GPUImageView) -> tuple[int, int]:
    """Canvas size minus the reserved overlay band on the height axis.

    The fit / centring / pan-clamp math targets this reduced area so the image
    never overlaps the bottom overlays. Width is unchanged — the band spans the
    full width and only steals vertical space. The height is floored at 1 so a
    viewport shorter than the reserved band can't drive the fit zoom negative.
    """
    canvas_w, canvas_h = canvas_size(view)
    return canvas_w, max(1, canvas_h - reserved_overlay_height(view))


def fit_zoom(view: GPUImageView) -> float:
    """Zoom level that fits the whole image above the overlays (capped at 1.0)."""
    img_w, img_h = _base_dimensions(view)
    w, h = content_size(view)
    return min(w / img_w, h / img_h, _MAX_FIT_ZOOM)


def fits_within_canvas(view: GPUImageView) -> bool:
    """True when the whole image is visible at the current zoom (no larger than
    the *full* canvas).

    A remembered "whole image" view must be re-fit to the content area so the
    overlay band letterboxes it above itself instead of cropping its bottom; a
    view zoomed in past this is left where the user left it.
    """
    img_w, img_h = _base_dimensions(view)
    w, h = canvas_size(view)
    full_fit = min(w / img_w, h / img_h, _MAX_FIT_ZOOM)
    return view.zoom <= full_fit * _FIT_EPSILON


def should_refit_on_load(was_remembered: bool, view: GPUImageView) -> bool:
    """Whether to content-fit an image on display.

    A fresh entry (``was_remembered`` False) always fits — so opening an image
    from the tile wall never inherits the previous view's leftover zoom. A
    genuinely remembered view is re-fit only when its whole image still fits the
    canvas; a real zoom-in is preserved.
    """
    return (not was_remembered) or fits_within_canvas(view)


def fit_to_window(view: GPUImageView) -> None:
    """自動縮放使圖片完整顯示在視窗內(覆蓋層上方的內容區)。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = content_size(view)
    view.zoom = fit_zoom(view)
    view.dz_offset_x = (w - img_w * view.zoom) / 2
    view.dz_offset_y = (h - img_h * view.zoom) / 2
    # Fresh fit → user hasn't panned / zoomed yet, so subsequent resizes
    # (docks settling, window maximised) keep the image centred instead of
    # hanging off-screen.
    view._user_locked_view = False


def fit_to_width(view: GPUImageView) -> None:
    """縮放使圖片寬度填滿視窗,垂直置中於覆蓋層上方的內容區。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = content_size(view)
    view.zoom = w / img_w
    view.dz_offset_x = 0
    view.dz_offset_y = (h - img_h * view.zoom) / 2
    view.update()


def fit_to_height(view: GPUImageView) -> None:
    """縮放使圖片高度填滿覆蓋層上方的內容區。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = content_size(view)
    view.zoom = h / img_h
    view.dz_offset_x = (w - img_w * view.zoom) / 2
    view.dz_offset_y = 0
    view.update()
