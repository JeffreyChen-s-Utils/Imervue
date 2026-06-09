"""Fit-to-window / width / height zoom + centring for :class:`GPUImageView`.

Computes the zoom and deep-zoom offsets that fit the current image to the
canvas. Reads the most-recent ``resizeGL`` size when available (it's
authoritative for the GL coordinate system and avoids the brief frames
where ``view.width()`` lags the actual layout).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_MAX_FIT_ZOOM = 1.0


def _canvas_size(view: GPUImageView) -> tuple[int, int]:
    """Return the logical canvas size, preferring the last resizeGL size."""
    if view._last_resize_size != (0, 0):
        return view._last_resize_size
    return view.width() or 1, view.height() or 1


def _base_dimensions(view: GPUImageView) -> tuple[int, int]:
    base = view.deep_zoom.levels[0]
    return base.shape[1], base.shape[0]


def fit_zoom(view: GPUImageView) -> float:
    """Zoom level that fits the whole image in the canvas (capped at 1.0)."""
    img_w, img_h = _base_dimensions(view)
    w, h = _canvas_size(view)
    return min(w / img_w, h / img_h, _MAX_FIT_ZOOM)


def fit_to_window(view: GPUImageView) -> None:
    """自動縮放使圖片完整顯示在視窗內。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = _canvas_size(view)
    view.zoom = fit_zoom(view)
    view.dz_offset_x = (w - img_w * view.zoom) / 2
    view.dz_offset_y = (h - img_h * view.zoom) / 2
    # Fresh fit → user hasn't panned / zoomed yet, so subsequent resizes
    # (docks settling, window maximised) keep the image centred instead of
    # hanging off-screen.
    view._user_locked_view = False


def fit_to_width(view: GPUImageView) -> None:
    """縮放使圖片寬度填滿視窗。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = view.width() or 1, view.height() or 1
    view.zoom = w / img_w
    view.dz_offset_x = 0
    view.dz_offset_y = (h - img_h * view.zoom) / 2
    view.update()


def fit_to_height(view: GPUImageView) -> None:
    """縮放使圖片高度填滿視窗。"""
    if not view.deep_zoom:
        return
    img_w, img_h = _base_dimensions(view)
    w, h = view.width() or 1, view.height() or 1
    view.zoom = h / img_h
    view.dz_offset_x = (w - img_w * view.zoom) / 2
    view.dz_offset_y = 0
    view.update()
