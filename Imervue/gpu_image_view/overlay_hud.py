"""Indicator and HUD layers of ``OverlayPainter``.

Zoom percentage, RGB histogram with clipping readout, animation frame
indicator, F3 OSD, Ctrl+F3 debug HUD and the transient quick-metadata HUD.
Mixed into :class:`~Imervue.gpu_image_view.overlay_painter.OverlayPainter`.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath

from Imervue.gpu_image_view.minimap import MINIMAP_MARGIN
from Imervue.gpu_image_view.osd_text import (
    debug_hud_lines,
    format_exif_osd_lines,
    osd_lines,
)
from Imervue.gpu_image_view.overlay_style import _FONT_CONSOLAS, _FONT_SEGOE_UI
from Imervue.image.histogram import compute_clipping, compute_histogram


class OverlayHudMixin:
    """Indicator, histogram, OSD and HUD overlay layers."""

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
        """Draw the RGB+luma histogram and the exposure-clipping readout."""
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
                cur_path, compute_histogram(img), compute_clipping(img),
            )
        if not view._histogram_cache:
            return
        _, hist, clip = view._histogram_cache
        self._draw_histogram_panel(painter, hist, clip)

    def _draw_histogram_panel(self, painter, hist, clip):  # pragma: no cover - GL paint
        hx, hy, hw, hh = 12, 12, 256, 120
        painter.fillRect(hx - 2, hy - 2, hw + 4, hh + 4, QColor(0, 0, 0, 140))
        h_max = max(hist.r.max(), hist.g.max(), hist.b.max(), hist.luma.max(), 1)
        # Luma sits behind as a faint grey backdrop; RGB curves draw over it.
        channels = (
            (hist.luma, QColor(200, 200, 200, 80)),
            (hist.r, QColor(220, 60, 60, 120)),
            (hist.g, QColor(60, 200, 60, 120)),
            (hist.b, QColor(60, 100, 220, 120)),
        )
        for counts, color in channels:
            path = QPainterPath()
            path.moveTo(hx, hy + hh)
            for i in range(256):
                path.lineTo(hx + i, hy + hh - counts[i] / h_max * hh)
            path.lineTo(hx + 255, hy + hh)
            path.closeSubpath()
            painter.fillPath(path, color)
        self._draw_clipping_readout(painter, clip, hx, hy, hw, hh)

    def _draw_clipping_readout(self, painter, clip, hx, hy, hw, hh):  # pragma: no cover - GL paint
        # Flag the clipped end of the range so the eye is drawn straight to it.
        if clip.over_fraction > 0:
            painter.fillRect(hx + hw - 3, hy, 3, hh, QColor(255, 70, 70, 200))
        if clip.under_fraction > 0:
            painter.fillRect(hx, hy, 3, hh, QColor(80, 130, 255, 200))
        font = QFont(_FONT_CONSOLAS)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(235, 235, 235, 220))
        painter.drawText(
            hx, hy + hh + 14,
            f"▲ {clip.over_fraction * 100:.1f}%"
            f"   ▼ {clip.under_fraction * 100:.1f}%",
        )

    def draw_anim_indicator(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the animation frame indicator (bottom centre)."""
        view = self.view
        anim = view._animation
        if not anim or not anim.is_animated:
            return

        from Imervue.gpu_image_view.actions.animation_player import anim_indicator_text
        text = anim_indicator_text(anim, view.main_window.language_wrapper.language_word_dict)

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
        lines = osd_lines(path, w, h) + self._exif_osd_lines(path)

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

    def _exif_osd_lines(self, path: str) -> list:  # pragma: no cover - file IO
        """Cached EXIF OSD lines for *path* (read once per image, not per frame)."""
        view = self.view
        cache = view._exif_osd_cache
        if cache and cache[0] == path:
            return cache[1]
        from Imervue.image.exif_merge import get_exif_data
        lines = format_exif_osd_lines(get_exif_data(Path(path)))
        view._exif_osd_cache = (path, lines)
        return lines

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

    def _quick_hud_active(self) -> bool:
        hud = getattr(self.view, "_quick_meta_hud", None)
        return bool(hud and hud[1] >= time.monotonic())

    def draw_quick_meta_hud(self, painter: QPainter):  # pragma: no cover - GL paint
        hud = getattr(self.view, "_quick_meta_hud", None)
        if not hud:
            return
        text, expires = hud
        if expires < time.monotonic():
            self.view._quick_meta_hud = None
            return
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(22)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 36
        h = fm.height() + 22
        x = int((self.view.width() - w) / 2)
        y = 28
        painter.fillRect(x, y, w, h, QColor(0, 0, 0, 185))
        painter.setPen(QColor(255, 235, 145))
        painter.drawText(x + 18, y + 12 + fm.ascent(), text)
