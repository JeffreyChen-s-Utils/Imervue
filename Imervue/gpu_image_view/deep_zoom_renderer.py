"""Deep-zoom tile + minimap GL rendering for :class:`GPUImageView`.

Extracted from the view alongside :mod:`tile_grid_renderer`. The renderer
walks the deep-zoom pyramid, draws every tile overlapping the viewport,
and paints the navigation minimap. It reads and mutates view state
(``zoom``, ``dz_offset_*``, ``tile_manager``, ``_minimap_tex`` …) directly.

Every method drives the live GL context, so they carry
``# pragma: no cover`` — they only run inside ``paintGL``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from OpenGL.GL import (
    GL_BLEND,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    glBlendFunc,
    glDeleteTextures,
    glDisable,
    glEnable,
    glLoadIdentity,
    glScalef,
    glTranslatef,
)

from Imervue.gpu_image_view.fit_view import canvas_size, reserved_overlay_height
from Imervue.gpu_image_view.minimap import minimap_geometry
from Imervue.gpu_image_view.tile_grid_renderer import upload_minimap_texture

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gpu_image_view.deep_zoom_renderer")

MINIMAP_OPACITY = 0.85
# Letterbox band fill — matches the GL clear colour so the reserved strip below
# the image reads as background, not a visible bar.
_LETTERBOX_RGBA = (0.1, 0.1, 0.1, 1.0)


def letterbox_band_rect(canvas_w: float, canvas_h: float,
                        reserved: float) -> tuple[float, float, float, float]:
    """Screen-space rect ``(x0, y0, x1, y1)`` of the reserved bottom band.

    Painted opaque over the deep-zoom image so a zoomed-in view's bottom edge is
    hidden and the minimap / filmstrip sit on a clean letterbox. ``y0`` is
    floored at 0 so an over-tall band can't start above the canvas.
    """
    top = max(0.0, canvas_h - reserved)
    return 0.0, top, canvas_w, canvas_h


def visible_tile_range(
    canvas_w: float, canvas_h: float,
    scale_x: float, scale_y: float,
    off_x: float, off_y: float, tile_size: int,
) -> tuple[int, int, int, int]:
    """Tile-index span ``(tx0, tx1, ty0, ty1)`` overlapping the viewport.

    ``canvas_w`` / ``canvas_h`` MUST be the same size the fit math centred
    against (see :func:`fit_view.canvas_size`); reading ``view.width()`` here
    while the fit used the resizeGL size makes the visible window disagree with
    where the image was placed. Pure so the index math is unit-testable.
    """
    left = -off_x / scale_x
    top = -off_y / scale_y
    right = left + canvas_w / scale_x
    bottom = top + canvas_h / scale_y
    return (int(left // tile_size), int(right // tile_size),
            int(top // tile_size), int(bottom // tile_size))


class DeepZoomRenderer:  # pragma: no cover - GL drawing path
    """Draw the deep-zoom tile pyramid and its minimap overlay."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view

    # -- deep-zoom tiles ---------------------------------------------

    def paint(self) -> None:
        view = self._view
        if not view.deep_zoom:
            return
        if view._slideshow_opacity < 1.0:
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        canvas = canvas_size(view)
        level, _ = view.deep_zoom.get_level(view.zoom)
        level_image = view.deep_zoom.levels[level]
        base_image = view.deep_zoom.levels[0]
        scale_x = view.zoom * (base_image.shape[1] / level_image.shape[1])
        scale_y = view.zoom * (base_image.shape[0] / level_image.shape[0])

        self._apply_transform(scale_x, scale_y, canvas)
        self._draw_visible_tiles(level, level_image, scale_x, scale_y, canvas)

        # 恢復 ortho MVP for other rendering
        if view.renderer.use_shaders:
            view.renderer.set_ortho(*canvas)

    def _apply_transform(self, scale_x: float, scale_y: float,
                         canvas: tuple[int, int]) -> None:
        """Push the scale+translate matrix mapping deep-zoom tile coords
        into widget pixels — shader path or fixed-function."""
        view = self._view
        if view.renderer.use_shaders:
            import numpy as _np
            from Imervue.gpu_image_view.gl_renderer import _ortho
            base_ortho = _ortho(0, canvas[0], canvas[1], 0, -1, 1)
            trans = _np.eye(4, dtype=_np.float32)
            trans[3, 0] = view.dz_offset_x / scale_x
            trans[3, 1] = view.dz_offset_y / scale_y
            scl = _np.eye(4, dtype=_np.float32)
            scl[0, 0] = scale_x
            scl[1, 1] = scale_y
            view.renderer.set_mvp(trans @ scl @ base_ortho)
            return
        glLoadIdentity()
        glScalef(scale_x, scale_y, 1)
        glTranslatef(view.dz_offset_x / scale_x, view.dz_offset_y / scale_y, 0)

    def _draw_visible_tiles(self, level: int, level_image,
                            scale_x: float, scale_y: float,
                            canvas: tuple[int, int]) -> None:
        """Walk the deep-zoom level and draw every tile that overlaps the
        current viewport, fetching textures lazily."""
        view = self._view
        tile_size = view.deep_zoom_tile_size
        h, w = level_image.shape[:2]

        tx0, tx1, ty0, ty1 = visible_tile_range(
            canvas[0], canvas[1], scale_x, scale_y,
            view.dz_offset_x, view.dz_offset_y, tile_size,
        )

        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                self._draw_one_tile(level, tx, ty, tile_size, w, h)

    def _draw_one_tile(self, level: int, tx: int, ty: int,
                       tile_size: int, w: int, h: int) -> None:
        """Draw a single deep-zoom tile if inside the level's bounds and
        its texture is ready."""
        if not (0 <= tx * tile_size < w and 0 <= ty * tile_size < h):
            return
        view = self._view
        tex = view.tile_manager.get_tile(level, tx, ty, tile_size)
        if tex is None:
            return
        tile_w = min(tile_size, w - tx * tile_size)
        tile_h = min(tile_size, h - ty * tile_size)
        x = tx * tile_size
        y = ty * tile_size
        view.renderer.draw_textured_quad(
            x, y, x + tile_w, y + tile_h, tex, view._slideshow_opacity,
        )

    # -- minimap ------------------------------------------------------

    def current_minimap_rect(self) -> tuple[int, int, int, int] | None:
        """Minimap rectangle (x, y, w, h) in widget coords, or None when no
        deep-zoom image is loaded. Shared by the painter and the click handler
        so the clickable area always matches what is drawn."""
        view = self._view
        if not view.deep_zoom:
            return None
        base = view.deep_zoom.levels[0]
        canvas_w, canvas_h = canvas_size(view)
        return minimap_geometry(
            canvas_w, canvas_h, base.shape[1], base.shape[0],
        )

    def paint_minimap(self) -> None:
        view = self._view
        rect = self.current_minimap_rect()
        if rect is None:
            return

        base = view.deep_zoom.levels[0]
        img_w, img_h = base.shape[1], base.shape[0]

        # 確保 ortho 回到畫面座標
        if not view.renderer.use_shaders:
            glLoadIdentity()

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._draw_letterbox_band()
        self._draw_minimap_background(rect)
        self._draw_minimap_thumbnail(rect)
        self._draw_viewport_box(rect, img_w, img_h)

    def _draw_letterbox_band(self) -> None:
        """Fill the reserved bottom band over the image so a zoomed-in view's
        bottom edge is hidden and the minimap / filmstrip sit on background.

        Drawn here (after the tiles, before the minimap, in screen-space ortho)
        rather than via a GL scissor on the tiles: scissoring leaks into Qt's
        QOpenGLWidget paint engine and was clipping the QPainter filmstrip out.

        Guarded so a band-fill failure can never abort ``paint_minimap`` (which
        would drop the minimap *and*, by skipping ``endNativePainting``, the
        QPainter filmstrip overlay too).
        """
        view = self._view
        try:
            reserved = reserved_overlay_height(view)
            if reserved <= 0:
                return
            canvas_w, canvas_h = canvas_size(view)
            x0, y0, x1, y1 = letterbox_band_rect(canvas_w, canvas_h, reserved)
            view.renderer.draw_colored_rect(x0, y0, x1, y1, *_LETTERBOX_RGBA)
        except Exception:  # noqa: BLE001 - never let the band break the overlays
            logger.exception("Letterbox band draw failed; skipping it this frame")

    def _draw_minimap_background(self, rect: tuple[int, int, int, int]) -> None:
        mm_x, mm_y, mm_w, mm_h = rect
        self._view.renderer.draw_colored_rect(
            mm_x - 2, mm_y - 2, mm_x + mm_w + 2, mm_y + mm_h + 2,
            0.0, 0.0, 0.0, 0.5,
        )

    def _draw_minimap_thumbnail(self, rect: tuple[int, int, int, int]) -> None:
        view = self._view
        mm_x, mm_y, mm_w, mm_h = rect
        thumb = view.deep_zoom.levels[-1]
        if view._minimap_dzi is not view.deep_zoom:
            # 重建 minimap texture
            if view._minimap_tex is not None:
                glDeleteTextures([view._minimap_tex])
            view._minimap_tex = upload_minimap_texture(thumb)
            view._minimap_dzi = view.deep_zoom
        view.renderer.draw_textured_quad(
            mm_x, mm_y, mm_x + mm_w, mm_y + mm_h, view._minimap_tex,
        )

    def _draw_viewport_box(self, rect: tuple[int, int, int, int],
                           img_w: int, img_h: int) -> None:
        view = self._view
        mm_x, mm_y, mm_w, mm_h = rect
        canvas_w, canvas_h = canvas_size(view)
        # 畫面可視區域在原圖座標
        vp_left = -view.dz_offset_x / view.zoom
        vp_top = -view.dz_offset_y / view.zoom
        vp_right = vp_left + canvas_w / view.zoom
        vp_bottom = vp_top + canvas_h / view.zoom

        sx = mm_w / img_w
        sy = mm_h / img_h
        rx0 = mm_x + max(0, vp_left * sx)
        ry0 = mm_y + max(0, vp_top * sy)
        rx1 = mm_x + min(mm_w, vp_right * sx)
        ry1 = mm_y + min(mm_h, vp_bottom * sy)

        view.renderer.draw_colored_rect(rx0, ry0, rx1, ry1, 1.0, 1.0, 1.0, 0.8, filled=False)
        glDisable(GL_BLEND)
