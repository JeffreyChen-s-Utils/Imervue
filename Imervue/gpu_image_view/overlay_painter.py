"""QPainter-based overlay (OSD / HUD / histogram / badges) for the viewer.

``GPUImageView`` owns one :class:`OverlayPainter` and delegates every
``QPainter`` overlay layer to it. The painter reads view state through the
``view`` back-reference but never touches the GL context — all of its drawing
goes onto an off-screen ``QImage`` composited by the view in ``_paint_overlay``.

Pure text/geometry helpers (``debug_hud_lines``, ``osd_lines``,
``place_hud_box``, ``visible_pixel_bounds``, ``favorites_set``) are module-level
functions so they can be unit-tested without a GL context.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen

from Imervue.gpu_image_view.minimap import MINIMAP_MARGIN

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_FONT_SEGOE_UI = "Segoe UI"
_FONT_CONSOLAS = "Consolas"

_BYTES_PER_MB = 1024 * 1024
_BYTES_PER_KB = 1024
_PIXEL_VIEW_ZOOM = 4.0
_PIXEL_GRID_MAX_CELLS = 40000


def human_file_size(path: str) -> str:
    """Return a human-readable size for ``path``, or "—" when unavailable."""
    try:
        size_bytes = os.path.getsize(path)
    except OSError:
        return "—"
    if size_bytes >= _BYTES_PER_MB:
        return f"{size_bytes / _BYTES_PER_MB:.2f} MB"
    return f"{size_bytes / _BYTES_PER_KB:.1f} KB"


def favorites_set(favorites) -> set:
    """Coerce a stored favorites value (set/list/None) into a set."""
    if isinstance(favorites, set):
        return favorites
    try:
        return set(favorites)
    except TypeError:
        return set()


def osd_lines(path: str, width: int, height: int) -> list[str]:
    """Build the three OSD text lines for ``path`` at ``width`` x ``height``."""
    suffix = Path(path).suffix.lstrip(".").upper() or "—"
    return [
        Path(path).name,
        f"{width} × {height}",
        f"{suffix}   {human_file_size(path)}",
    ]


def debug_hud_lines(stats: dict) -> list[str]:
    """Build the Debug-HUD text lines from a stats dict.

    Keys: vram_usage, vram_limit, tile_tex, tile_cache, prefetch,
    prefetch_workers, active_threads, max_threads, generation, zoom.
    """
    vram_mb = stats["vram_usage"] / _BYTES_PER_MB
    limit_mb = stats["vram_limit"] / _BYTES_PER_MB
    pct = (stats["vram_usage"] / stats["vram_limit"] * 100) if stats["vram_limit"] else 0
    return [
        f"VRAM  {vram_mb:6.1f} / {limit_mb:6.1f} MB  ({pct:4.1f}%)",
        f"Tile tex   {stats['tile_tex']:4d}   cache {stats['tile_cache']:4d}",
        f"Prefetch   {stats['prefetch']:4d}   workers {stats['prefetch_workers']}",
        f"Threads    {stats['active_threads']:4d} / {stats['max_threads']}",
        f"Gen {stats['generation']}   Zoom {stats['zoom'] * 100:.1f}%",
    ]


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
    """Clamp the visible image-pixel rectangle to the image bounds."""
    left = -off_x / zoom
    top = -off_y / zoom
    right = left + view_w / zoom
    bottom = top + view_h / zoom
    return (
        max(0, int(left)), max(0, int(top)),
        min(img_w, int(right) + 1), min(img_h, int(bottom) + 1),
    )


class OverlayPainter:
    """Draws every ``QPainter`` overlay layer for a ``GPUImageView``."""

    _MINIMAP_OPACITY = 0.85

    def __init__(self, view: GPUImageView) -> None:
        self.view = view
        self._placeholder_timer: QTimer | None = None

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def collect_layers(self) -> list:
        """Return active overlay layers in draw order (callables p -> None)."""
        view = self.view
        zoom_active = bool((not view.tile_grid_mode) and view.deep_zoom)
        anim_active = bool(view._animation and view._animation.is_animated)
        pixel_active = zoom_active and view._pixel_view and view.zoom >= _PIXEL_VIEW_ZOOM

        layer_table: list[tuple[bool, object]] = [
            (
                view.tile_grid_mode and bool(view.tile_rects),
                [self.draw_tile_labels, self.draw_tile_badges,
                 self.draw_tile_placeholders],
            ),
            (zoom_active, self.draw_zoom_indicator),
            (zoom_active and view._show_histogram, self.draw_histogram),
            (anim_active, self.draw_anim_indicator),
            (zoom_active and view._show_osd, self.draw_osd),
            (view._show_debug_hud, self.draw_debug_hud),
            (pixel_active, self.draw_pixel_view),
        ]
        candidates: list = []
        for active, painter in layer_table:
            if not active:
                continue
            if isinstance(painter, list):
                candidates += painter
            else:
                candidates.append(painter)
        return candidates

    def paint(self, painter: QPainter) -> None:  # pragma: no cover - GL compositing
        layers = self.collect_layers()
        if not layers:
            return
        view = self.view
        dpr = view.devicePixelRatio()
        w, h = view.width(), view.height()
        img = QImage(int(w * dpr), int(h * dpr),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        for layer in layers:
            layer(p)
        p.end()
        painter.drawImage(0, 0, img)

    # ------------------------------------------------------------------
    # Tile labels + badges
    # ------------------------------------------------------------------
    def draw_tile_labels(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the file-name caption under each thumbnail."""
        view = self.view
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()

        for x0, _y0, x1, y1, path in view.tile_rects:
            name = Path(path).stem
            tw = x1 - x0
            elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(tw))
            tx = int(x0 + (tw - fm.horizontalAdvance(elided)) / 2)
            ty = int(y1 + fm.ascent() + 2)
            if ty < view.height() + fm.height():
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(tx + 1, ty + 1, elided)
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(tx, ty, elided)

    def draw_tile_badges(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw rating / favorite / bookmark / colour-label badges per tile."""
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        from Imervue.user_settings.color_labels import _store as _color_store

        ratings = user_setting_dict.get("image_ratings", {}) or {}
        favs = favorites_set(user_setting_dict.get("image_favorites", set()))
        color_store = _color_store()

        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)

        for x0, y0, x1, y1, path in self.view.tile_rects:
            color_name = color_store.get(path)
            _paint_color_strip(painter, x0, y0, y1, color_name)
            _paint_favorite_badge(painter, x0, y0, path in favs, color_name)
            _paint_bookmark_badge(painter, x0, y0, x1, path)
            _paint_rating_badge(painter, x0, y1, ratings.get(path, 0))

    def draw_tile_placeholders(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw a rotating dot spinner on tile slots without a thumbnail yet."""
        view = self.view
        rects = getattr(view, "placeholder_rects", None)
        if not rects:
            return

        phase = (time.monotonic() % 1.0) * 2 * 3.14159
        painter.setPen(QColor(140, 140, 140, 200))
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(11)
        painter.setFont(font)

        for x0, y0, x1, y1 in rects:
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            radius = min(x1 - x0, y1 - y0) * 0.12
            for i in range(4):
                angle = phase + i * (3.14159 / 2)
                dot_x = cx + radius * 1.6 * np.cos(angle)
                dot_y = cy + radius * 1.6 * np.sin(angle)
                alpha = 80 + int(120 * (i / 3))
                painter.setBrush(QColor(200, 200, 200, alpha))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    int(dot_x - radius / 3), int(dot_y - radius / 3),
                    int(radius * 2 / 3), int(radius * 2 / 3),
                )

        if self._placeholder_timer is None:
            timer = QTimer(view)
            timer.setInterval(80)
            timer.timeout.connect(self.tick_placeholder)
            self._placeholder_timer = timer
        if not self._placeholder_timer.isActive():
            self._placeholder_timer.start()

    def tick_placeholder(self) -> None:
        view = self.view
        if view.tile_grid_mode and getattr(view, "placeholder_rects", None):
            view.update()
        elif self._placeholder_timer and self._placeholder_timer.isActive():
            self._placeholder_timer.stop()

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------
    def draw_zoom_indicator(self, painter: QPainter):  # pragma: no cover - GL paint
        """Show the zoom percentage above the minimap (or bottom-right)."""
        view = self.view
        pct = f"{view.zoom * 100:.0f}%"
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(pct)
        x = view.width() - tw - MINIMAP_MARGIN - 2
        rect = view._current_minimap_rect()
        if rect is not None:
            y = view.height() - MINIMAP_MARGIN - rect[3] - fm.height() - 4
        else:
            y = view.height() - MINIMAP_MARGIN - 8

        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawText(x + 1, y + 1, pct)
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, pct)

    def draw_histogram(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the RGB histogram overlay (top-left)."""
        view = self.view
        if not view.deep_zoom:
            return
        images = view.model.images
        if not images or view.current_index >= len(images):
            return
        cur_path = images[view.current_index]
        cache = view._histogram_cache
        if cur_path and (not cache or cache[0] != cur_path):
            img = view.deep_zoom.levels[-1]
            view._histogram_cache = (
                cur_path,
                np.histogram(img[:, :, 0], bins=256, range=(0, 256))[0],
                np.histogram(img[:, :, 1], bins=256, range=(0, 256))[0],
                np.histogram(img[:, :, 2], bins=256, range=(0, 256))[0],
            )

        if not view._histogram_cache:
            return

        _, hr, hg, hb = view._histogram_cache
        h_max = max(hr.max(), hg.max(), hb.max(), 1)
        hx, hy, hw, hh = 12, 12, 256, 120
        painter.fillRect(hx - 2, hy - 2, hw + 4, hh + 4, QColor(0, 0, 0, 140))

        for hist, color in [(hr, QColor(220, 60, 60, 120)),
                            (hg, QColor(60, 200, 60, 120)),
                            (hb, QColor(60, 100, 220, 120))]:
            path = QPainterPath()
            path.moveTo(hx, hy + hh)
            for i in range(256):
                bh = hist[i] / h_max * hh
                path.lineTo(hx + i, hy + hh - bh)
            path.lineTo(hx + 255, hy + hh)
            path.closeSubpath()
            painter.fillPath(path, color)

    def draw_anim_indicator(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the animation frame indicator (bottom centre)."""
        view = self.view
        anim = view._animation
        if not anim or not anim.is_animated:
            return

        lang = view.main_window.language_wrapper.language_word_dict
        frame_text = lang.get("anim_frame_indicator", "Frame {current}/{total}").format(
            current=anim.current_frame + 1, total=anim.total_frames
        )
        status = (
            lang.get("anim_play", "Play") if not anim.playing
            else lang.get("anim_pause", "Pause")
        )
        speed_text = lang.get("anim_speed", "Speed: {speed}x").format(speed=f"{anim.speed:.1f}")
        text = f"{status}  |  {frame_text}  |  {speed_text}"

        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        x = (view.width() - tw) // 2
        y = view.height() - 20

        painter.fillRect(x - 8, y - th - 2, tw + 16, th + 8, QColor(0, 0, 0, 160))
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(x, y, text)

    # ------------------------------------------------------------------
    # OSD + Debug HUD
    # ------------------------------------------------------------------
    def draw_osd(self, painter: QPainter):  # pragma: no cover - GL paint
        """F3 OSD — file name / size / format in the top-right corner."""
        view = self.view
        path = view._current_path()
        if not path or not view.deep_zoom:
            return
        base = view.deep_zoom.levels[0]
        h, w = base.shape[:2]
        lines = osd_lines(path, w, h)

        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(13)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 10, 6
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        x = view.width() - box_w - 12
        y = 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 170))
        painter.setPen(QColor(230, 230, 230))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    def draw_debug_hud(self, painter: QPainter):  # pragma: no cover - GL paint
        """Ctrl+F3 Debug HUD — VRAM / cache / thread-pool stats."""
        view = self.view
        stats = {
            "vram_usage": view._vram_usage,
            "vram_limit": view._vram_limit,
            "tile_tex": len(view.tile_textures),
            "tile_cache": len(view.tile_cache),
            "prefetch": len(view._prefetch_cache),
            "prefetch_workers": len(view._prefetch_workers),
            "active_threads": view.thread_pool.activeThreadCount(),
            "max_threads": view.thread_pool.maxThreadCount(),
            "generation": view._load_generation,
            "zoom": view.zoom,
        }
        lines = debug_hud_lines(stats)

        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(12)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 8, 5
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        x = 12
        y = view.height() - box_h - 12

        painter.fillRect(x, y, box_w, box_h, QColor(0, 0, 0, 180))
        painter.setPen(QColor(120, 220, 120))
        for i, line in enumerate(lines):
            painter.drawText(x + pad_x, y + pad_y + fm.ascent() + i * line_h, line)

    # ------------------------------------------------------------------
    # Pixel view
    # ------------------------------------------------------------------
    def draw_pixel_view(self, painter: QPainter):  # pragma: no cover - GL paint
        """Shift+P — pixel grid + hover RGB when zoom >= 4x."""
        view = self.view
        if not view.deep_zoom or view.zoom < _PIXEL_VIEW_ZOOM:
            return
        base = view.deep_zoom.levels[0]
        h, w = base.shape[:2]
        x0, y0, x1, y1 = visible_pixel_bounds(
            view.zoom, view.dz_offset_x, view.dz_offset_y,
            view.width(), view.height(), w, h,
        )
        if (x1 - x0) * (y1 - y0) <= _PIXEL_GRID_MAX_CELLS:
            self._draw_pixel_grid(painter, x0, y0, x1, y1)
        if view._hover_image_xy is not None:
            cx, cy = view._hover_image_xy
            if 0 <= cx < w and 0 <= cy < h:
                self._draw_hover_pixel_hud(painter, base, cx, cy)

    def _draw_pixel_grid(self, painter: QPainter,  # pragma: no cover - GL paint
                         x0: int, y0: int, x1: int, y1: int) -> None:
        view = self.view
        pen = QPen(QColor(128, 128, 128, 120))
        pen.setWidth(0)
        painter.setPen(pen)
        y_top = int(y0 * view.zoom + view.dz_offset_y)
        y_bot = int(y1 * view.zoom + view.dz_offset_y)
        for gx in range(x0, x1 + 1):
            sx = int(gx * view.zoom + view.dz_offset_x)
            painter.drawLine(sx, y_top, sx, y_bot)
        x_left = int(x0 * view.zoom + view.dz_offset_x)
        x_right = int(x1 * view.zoom + view.dz_offset_x)
        for gy in range(y0, y1 + 1):
            sy = int(gy * view.zoom + view.dz_offset_y)
            painter.drawLine(x_left, sy, x_right, sy)

    def _draw_hover_pixel_hud(self, painter: QPainter,  # pragma: no cover - GL paint
                              base, cx: int, cy: int) -> None:
        view = self.view
        pixel = base[cy, cx]
        r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
        a = int(pixel[3]) if base.shape[2] >= 4 else 255
        lines = [
            f"({cx}, {cy})",
            f"RGB {r:3d} {g:3d} {b:3d}",
            f"A   {a:3d}    #{r:02X}{g:02X}{b:02X}",
        ]
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(12)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 6, 4
        line_h = fm.height()
        box_w = max(fm.horizontalAdvance(line) for line in lines) + pad_x * 2
        box_h = line_h * len(lines) + pad_y * 2
        sx = cx * view.zoom + view.dz_offset_x
        sy = cy * view.zoom + view.dz_offset_y
        size = view.zoom
        _draw_hover_pixel_outline(painter, sx, sy, size)
        hx, hy = place_hud_box(int(sx), int(sy), int(size), box_w, box_h,
                               view.width(), view.height())
        painter.fillRect(hx, hy, box_w, box_h, QColor(0, 0, 0, 190))
        painter.setPen(QColor(240, 240, 240))
        for i, line in enumerate(lines):
            painter.drawText(hx + pad_x, hy + pad_y + fm.ascent() + i * line_h, line)
        painter.fillRect(hx + box_w - 20, hy + pad_y, 14, 14, QColor(r, g, b))


def _paint_color_strip(painter, x0, y0, y1, color_name) -> None:  # pragma: no cover - GL paint
    """Left-edge 6 px colour-label strip; skipped when no label is set."""
    from Imervue.user_settings.color_labels import COLOR_RGB
    if not color_name or color_name not in COLOR_RGB:
        return
    r, g, b = COLOR_RGB[color_name]
    painter.fillRect(int(x0), int(y0), 6, int(y1 - y0), QColor(r, g, b, 230))


def _paint_favorite_badge(painter, x0, y0, is_fav: bool,  # pragma: no cover - GL paint
                          color_name) -> None:
    if not is_fav:
        return
    offset = 10 if color_name else 4
    painter.fillRect(int(x0 + offset), int(y0 + 4), 18, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 90, 120))
    painter.drawText(int(x0 + offset + 2), int(y0 + 18), "♥")


def _paint_bookmark_badge(painter, x0, y0, x1, path: str) -> None:  # pragma: no cover - GL paint
    from Imervue.user_settings.bookmark import is_bookmarked
    if not is_bookmarked(path):
        return
    painter.fillRect(int(x1 - 22), int(y0 + 4), 18, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 210, 80))
    painter.drawText(int(x1 - 20), int(y0 + 18), "★")


def _paint_rating_badge(painter, x0, y1, rating: int) -> None:  # pragma: no cover - GL paint
    if not rating or rating <= 0:
        return
    badge_text = "★" * int(rating)
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(badge_text)
    painter.fillRect(int(x0 + 4), int(y1 - 20), tw + 8, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 210, 80))
    painter.drawText(int(x0 + 8), int(y1 - 6), badge_text)


def _draw_hover_pixel_outline(painter: QPainter,  # pragma: no cover - GL paint
                              sx: float, sy: float, size: float) -> None:
    pen = QPen(QColor(255, 220, 0, 230))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(int(sx), int(sy), int(size), int(size))
