"""Tile-wall (thumbnail grid) GL rendering for :class:`GPUImageView`.

Extracted from the view so the QWidget keeps only the GL lifecycle and
event plumbing. The renderer reads and mutates view state (``tile_rects``,
``tile_textures``, ``placeholder_rects`` …) directly; it is a pure drawing
collaborator with no state of its own beyond a back-reference to the view.

All methods touch the live GL context, so they carry ``# pragma: no cover``
— they only run inside ``paintGL`` under a real context, which the headless
CI cannot exercise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_LINE_LOOP,
    GL_LINES,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TRIANGLE_FAN,
    GL_UNPACK_ALIGNMENT,
    glBegin,
    glBlendFunc,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glLineWidth,
    glLoadIdentity,
    glPixelStorei,
    glVertex2f,
)

from Imervue.gpu_image_view.texture_upload import prepare_rgba, upload_rgba_texture
from Imervue.gpu_image_view.tile_focus import focus_tile_rect
from Imervue.gpu_image_view.tile_layout import tile_grid_layout

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Default layout base when no thumbnail size and no cache sample exist.
_DEFAULT_TILE_BASE = 256
# Selection-marker geometry (blue check circle in the tile corner).
_MARKER_CIRCLE_RADIUS = 9
_MARKER_CIRCLE_SEGMENTS = 32
_TWO_PI = 2.0 * 3.1415926
# Keyboard-focus ring — warm amber so it reads distinctly from the blue
# selection marker even when the focused tile is also selected.
_FOCUS_COLOR = (1.0, 0.78, 0.16, 1.0)
_FOCUS_BORDER_WIDTH = 3


class TileGridRenderer:  # pragma: no cover - GL drawing path
    """Draw the thumbnail wall and its selection overlays."""

    def __init__(self, view: GPUImageView) -> None:
        self._view = view

    # -- layout -------------------------------------------------------

    def base_size(self) -> int:
        view = self._view
        if view.thumbnail_size is not None:
            return view.thumbnail_size
        if view.tile_cache:
            # 用第一張圖實際寬度當排版基準
            return next(iter(view.tile_cache.values())).shape[1]
        return _DEFAULT_TILE_BASE

    # -- per-tile draw ------------------------------------------------

    def _draw_placeholder(self, x0: float, y0: float,
                          scaled_tile: float, vw: int, vh: int) -> None:
        x1, y1 = x0 + scaled_tile, y0 + scaled_tile
        if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
            return
        renderer = self._view.renderer
        renderer.draw_colored_rect(x0, y0, x1, y1, 0.14, 0.14, 0.14, 1.0, filled=True)
        renderer.draw_colored_rect(x0, y0, x1, y1, 0.28, 0.28, 0.28, 1.0, filled=False)
        self._view.placeholder_rects.append((x0, y0, x1, y1))

    def _draw_single(self, i: int, path: str, cols: int, cell: float,
                     scaled_tile: float, vw: int, vh: int) -> None:
        view = self._view
        row, col = divmod(i, cols)
        x0 = col * cell + view.grid_offset_x
        y0 = row * cell + view.grid_offset_y
        if path not in view.tile_cache:
            self._draw_placeholder(x0, y0, scaled_tile, vw, vh)
            return
        img_data = view.tile_cache[path]
        x1 = x0 + img_data.shape[1] * view._tile_draw_scale
        y1 = y0 + img_data.shape[0] * view._tile_draw_scale
        if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
            return
        view.tile_rects.append((x0, y0, x1, y1, path))
        if not view._ensure_tile_texture(path, img_data):
            return
        view.renderer.draw_textured_quad(x0, y0, x1, y1, view.tile_textures[path])

    # -- overlays -----------------------------------------------------

    def _draw_grid_borders(self) -> None:
        view = self._view
        if not view.tile_rects:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1)
        for x0, y0, x1, y1, _path in view.tile_rects:
            view.renderer.draw_colored_rect(x0, y0, x1, y1, 0.3, 0.3, 0.3, 1.0, filled=False)
        glEnable(GL_TEXTURE_2D)

    def _draw_selection_marker(self, x0, y0, x1, y1) -> None:
        # 藍色粗邊框
        glColor4f(0.18, 0.5, 1.0, 1.0)
        glBegin(GL_LINE_LOOP)
        for (vx, vy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            glVertex2f(vx, vy)
        glEnd()
        # 右上藍色圓 + 勾
        cx, cy = x1 - 12, y0 + 12
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(cx, cy)
        for i in range(_MARKER_CIRCLE_SEGMENTS + 1):
            angle = i * _TWO_PI / _MARKER_CIRCLE_SEGMENTS
            glVertex2f(cx + _MARKER_CIRCLE_RADIUS * np.cos(angle),
                       cy + _MARKER_CIRCLE_RADIUS * np.sin(angle))
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glLineWidth(2.5)
        glBegin(GL_LINES)
        glVertex2f(cx - 4, cy)
        glVertex2f(cx - 1, cy + 3)
        glVertex2f(cx - 1, cy + 3)
        glVertex2f(cx + 5, cy - 4)
        glEnd()
        glLineWidth(4)

    def _draw_selection_overlay(self) -> None:
        view = self._view
        if not view.tile_selection_mode:
            return
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(4)
        for x0, y0, x1, y1, path in view.tile_rects:
            if path in view.selected_tiles:
                self._draw_selection_marker(x0, y0, x1, y1)
        glDisable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)
        glLineWidth(1)

    def _draw_focus_marker(self, cols: int, cell: float,
                           scaled_tile: float, vw: int, vh: int) -> None:
        view = self._view
        idx = view.focused_tile_index
        if not 0 <= idx < len(view.model.images):
            return
        rect = focus_tile_rect(idx, cols, cell, scaled_tile,
                               view.grid_offset_x, view.grid_offset_y)
        x0, y0, x1, y1 = rect
        if x1 < 0 or x0 > vw or y1 < 0 or y0 > vh:
            return
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(_FOCUS_BORDER_WIDTH)
        glColor4f(*_FOCUS_COLOR)
        glBegin(GL_LINE_LOOP)
        for (vx, vy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            glVertex2f(vx, vy)
        glEnd()
        glDisable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)
        glLineWidth(1)

    def _draw_drag_rect(self) -> None:
        view = self._view
        if not (view._drag_selecting and view._drag_start_pos and view._drag_end_pos):
            return
        x0, y0 = view._drag_start_pos.x(), view._drag_start_pos.y()
        x1, y1 = view._drag_end_pos.x(), view._drag_end_pos.y()
        left, right = min(x0, x1), max(x0, x1)
        top, bottom = min(y0, y1), max(y0, y1)
        corners = ((left, top), (right, top), (right, bottom), (left, bottom))
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # 淡藍填充
        glColor4f(0.18, 0.5, 1.0, 0.08)
        glBegin(GL_QUADS)
        for (vx, vy) in corners:
            glVertex2f(vx, vy)
        glEnd()
        # 藍色粗框
        glColor4f(0.18, 0.5, 1.0, 1.0)
        glLineWidth(3)
        glBegin(GL_LINE_LOOP)
        for (vx, vy) in corners:
            glVertex2f(vx, vy)
        glEnd()
        glDisable(GL_BLEND)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)

    # -- entry point --------------------------------------------------

    def paint(self) -> None:
        """Draw the full thumbnail wall for the current frame."""
        view = self._view
        glLoadIdentity()
        # 預先淘汰超出 VRAM 上限的紋理（不在逐 tile 迴圈中做）
        view._evict_tile_textures_if_needed()

        images = view.model.images
        base_tile = self.base_size()
        view._tile_draw_scale, cell, cols = tile_grid_layout(
            view.width(), base_tile, view.tile_scale,
            view.tile_padding, view.devicePixelRatio(),
        )
        scaled_tile = base_tile * view._tile_draw_scale
        view.tile_rects = []
        # Placeholders for tiles whose thumbnail hasn't arrived yet — rendered
        # as dark squares so the grid layout is visible immediately. Stored in
        # screen coords; consumed by the overlay painter.
        view.placeholder_rects = []

        # 在迴圈外設定一次 GL 狀態，避免每張 tile 都重複呼叫
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        vw, vh = view.width(), view.height()
        for i, path in enumerate(images):
            self._draw_single(i, path, cols, cell, scaled_tile, vw, vh)

        self._draw_grid_borders()
        self._draw_selection_overlay()
        self._draw_focus_marker(cols, cell, scaled_tile, vw, vh)
        self._draw_drag_rect()


def upload_minimap_texture(thumb) -> int:  # pragma: no cover - GL upload path
    """Upload a deep-zoom thumbnail as the minimap texture (no edge clamp)."""
    return upload_rgba_texture(prepare_rgba(thumb), clamp_to_edge=False)
