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

import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from Imervue.gpu_image_view.filmstrip import (
    BAND_VPAD,
    ITEM_HEIGHT,
    ITEM_WIDTH,
    compute_filmstrip_items,
    filmstrip_band,
    fit_rect_centered,
)
from Imervue.gpu_image_view.minimap import MINIMAP_MARGIN
from Imervue.gpu_image_view.video_badge import video_badge_geometry
from Imervue.gpu_image_view.view_animator import THUMB_FADE_MS
from Imervue.image.histogram import compute_clipping, compute_histogram
from Imervue.image.video_frames import is_video_path

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gpu_image_view.overlay_painter")

_FONT_SEGOE_UI = "Segoe UI"
_FONT_CONSOLAS = "Consolas"


def _run_overlay_layers(p: QPainter, layers: list) -> list[str]:
    """Call each ``layer(p)``, isolating failures.

    Every overlay layer is composited onto one off-screen image that is blitted
    in a single ``drawImage`` at the end, so an unguarded exception in any one
    layer would discard the WHOLE overlay (filmstrip + chrome) for the frame —
    and, by unwinding past the view's ``painter.end()``, leave the widget
    QPainter open and corrupt the next GL frame (dropping the minimap too).
    Guarding each layer keeps one bad layer from taking the rest down; the
    failure is logged so the real cause surfaces. Returns the names of the
    layers that raised.
    """
    failed: list[str] = []
    for layer in layers:
        try:
            layer(p)
        except Exception:  # noqa: BLE001 - one bad layer must not drop the overlay
            name = getattr(layer, "__name__", repr(layer))
            logger.exception("Overlay layer %s failed; skipped this frame", name)
            failed.append(name)
    return failed
# Repaint cadence for the tile-wall placeholder spinner + fade-in pump.
_PLACEHOLDER_TICK_MS = 80

_BYTES_PER_MB = 1024 * 1024
_BYTES_PER_KB = 1024
_PIXEL_VIEW_ZOOM = 4.0
_PIXEL_GRID_MAX_CELLS = 40000
# Loupe magnifier (toggle with L in deep zoom).
LOUPE_BOX_PX = 170
LOUPE_MAGNIFICATION = 4
_LOUPE_MAG_MIN = 2
_LOUPE_MAG_MAX = 16
_LOUPE_CURSOR_GAP = 24
_LOUPE_BORDER_RGBA = (255, 255, 255, 210)
_LOUPE_CROSSHAIR_RGBA = (255, 80, 80, 200)
# Filmstrip band background + current-item highlight (amber, matching the
# tile-wall keyboard focus ring).
_FILMSTRIP_BAND_RGBA = (0, 0, 0, 150)
_FILMSTRIP_PLACEHOLDER_RGBA = (40, 40, 40, 200)
_FILMSTRIP_HIGHLIGHT_RGBA = (255, 199, 41, 255)
_FILMSTRIP_BORDER_WIDTH = 3
_LOADING_PILL_RGBA = (0, 0, 0, 170)
# Video ▶ badge — translucent disc + opaque white play triangle.
_VIDEO_BADGE_DISC_RGBA = (0, 0, 0, 150)
_VIDEO_BADGE_TRI_RGBA = (255, 255, 255, 235)
# Rubber-band zoom selection rectangle (deep zoom).
_ZOOM_BAND_FILL_RGBA = (70, 140, 255, 40)
_ZOOM_BAND_BORDER_RGBA = (70, 140, 255, 220)
_ZOOM_BAND_BORDER_WIDTH = 2


def _rgba_to_pixmap(arr: np.ndarray) -> QPixmap:
    """Convert an H×W×4 uint8 RGBA array into a detached :class:`QPixmap`.

    ``.copy()`` detaches the ``QImage`` from the numpy buffer before the array
    can be freed (the established project idiom for numpy → Qt image handoff).
    """
    contiguous = np.ascontiguousarray(arr)
    height, width = contiguous.shape[:2]
    qimg = QImage(contiguous.data, width, height, width * 4,
                  QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)


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


def _exif_to_float(value) -> float | None:
    """Coerce an EXIF value (IFDRational / (num, den) / number) to a float."""
    if value is None:
        return None
    try:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            num, den = value
            return num / den if den else None
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _format_exposure(value) -> str | None:
    seconds = _exif_to_float(value)
    if seconds is None or seconds <= 0:
        return None
    if seconds >= 1:  # NOSONAR S2583 - FP: _exif_to_float can return (0, 1), e.g. 1/200s
        return f"{seconds:g}s"
    return f"1/{round(1 / seconds)}s"


def _format_iso(value) -> str | None:
    if isinstance(value, (tuple, list)) and value:
        value = value[0]
    try:
        return f"ISO {int(value)}"
    except (TypeError, ValueError):
        return None


def format_exif_osd_lines(exif: dict) -> list[str]:
    """Build compact OSD lines (exposure / f-number / ISO / focal + lens).

    Returns an empty list when no shooting data is present, so non-photo images
    leave the OSD unchanged. Each field is skipped individually when missing or
    malformed, so partial EXIF still yields a useful line.
    """
    if not exif:
        return []
    fnumber = _exif_to_float(exif.get("FNumber"))
    focal = _exif_to_float(exif.get("FocalLength"))
    fields = [
        _format_exposure(exif.get("ExposureTime")),
        f"f/{fnumber:g}" if fnumber and fnumber > 0 else None,
        _format_iso(exif.get("ISOSpeedRatings")),
        f"{round(focal)}mm" if focal and focal > 0 else None,
    ]
    primary = [field for field in fields if field]
    lines = ["   ".join(primary)] if primary else []
    lens = exif.get("LensModel")
    if lens and str(lens).strip():
        lines.append(str(lens).strip())
    return lines


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
        filmstrip_active = bool(
            (not view.tile_grid_mode) and view._filmstrip_enabled
            and len(view.model.images) > 1
        )
        loading_active = bool(
            view._deep_zoom_loading and view.deep_zoom is None
            and not view.tile_grid_mode
        )

        loupe_active = (zoom_active and view._loupe_enabled
                        and view._hover_image_xy is not None)
        band_active = bool(view._zoom_band_active and view._zoom_band_start
                           and view._zoom_band_end)
        layer_table: list[tuple[bool, object]] = [
            (view.tile_grid_mode and bool(view.tile_rects), self.draw_tile_overlays),
            # Low-res preview sits in the background, below the filmstrip and
            # chrome; the "Loading…" pill is added last so it stays on top.
            (loading_active, self.draw_loading_preview),
            (filmstrip_active, self.draw_filmstrip),
            (zoom_active, self.draw_zoom_indicator),
            (zoom_active and view._show_histogram, self.draw_histogram),
            (anim_active, self.draw_anim_indicator),
            (zoom_active and view._show_osd, self.draw_osd),
            (view._show_debug_hud, self.draw_debug_hud),
            (pixel_active, self.draw_pixel_view),
            (loupe_active, self.draw_loupe),
            (band_active, self.draw_zoom_band),
            (zoom_active and self._current_is_video(), self.draw_video_badge),
            (loading_active, self.draw_loading_pill),
        ]
        return [painter for active, painter in layer_table if active]

    def _current_is_video(self) -> bool:
        """True when the deep-zoom image is a video (so it shows a play badge)."""
        view = self.view
        images = getattr(getattr(view, "model", None), "images", None) or []
        idx = getattr(view, "current_index", -1)
        return bool(0 <= idx < len(images) and is_video_path(images[idx]))

    def draw_video_badge(self, painter: QPainter):  # pragma: no cover - GL paint
        """Centre a play badge over a deep-zoom video poster."""
        view = self.view
        _paint_play_badge(painter, video_badge_geometry(0, 0, view.width(), view.height()))

    def draw_tile_overlays(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the tile-wall QPainter overlays (labels, badges, placeholders)."""
        self.draw_tile_labels(painter)
        self.draw_tile_badges(painter)
        self.draw_tile_placeholders(painter)

    def paint(self, painter: QPainter) -> None:  # pragma: no cover - GL compositing
        try:
            layers = self.collect_layers()
        except Exception:  # noqa: BLE001 - layer selection must not drop the overlay
            logger.exception("Overlay layer collection failed this frame")
            return
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
        _run_overlay_layers(p, layers)
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
            _paint_bookmark_badge(painter, y0, x1, path)
            _paint_rating_badge(painter, x0, y1, ratings.get(path, 0))
            if is_video_path(path):
                _paint_play_badge(painter, video_badge_geometry(x0, y0, x1, y1))

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

        self.ensure_fade_pump()

    def tick_placeholder(self) -> None:
        view = self.view
        if view.tile_grid_mode and (getattr(view, "placeholder_rects", None)
                                    or self._tiles_fading()):
            view.update()
        elif self._placeholder_timer and self._placeholder_timer.isActive():
            self._placeholder_timer.stop()

    def _tiles_fading(self) -> bool:
        """True while any tile is still within its fade-in window."""
        times = getattr(self.view, "_tile_load_times", None)
        if not times:
            return False
        now = time.monotonic()
        return any((now - start) * 1000 < THUMB_FADE_MS for start in times.values())

    def ensure_fade_pump(self) -> None:
        """Start the repaint timer so freshly loaded tiles animate their fade.

        Called when a thumbnail arrives even if no placeholders remain, so the
        last tiles of a folder still fade in smoothly rather than popping.
        """
        if self._placeholder_timer is None:
            timer = QTimer(self.view)
            timer.setInterval(_PLACEHOLDER_TICK_MS)
            timer.timeout.connect(self.tick_placeholder)
            self._placeholder_timer = timer
        if not self._placeholder_timer.isActive():
            self._placeholder_timer.start()

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
        from Imervue.image.info import get_exif_data
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

    # ------------------------------------------------------------------
    # Filmstrip + loading feedback
    # ------------------------------------------------------------------
    def draw_filmstrip(self, painter: QPainter):  # pragma: no cover - GL paint
        """Bottom-of-screen strip of neighbour thumbnails (deep-zoom only)."""
        view = self.view
        images = view.model.images
        strip_width = view._browse.filmstrip_strip_width()
        items = compute_filmstrip_items(
            enabled=view._filmstrip_enabled, in_grid_mode=view.tile_grid_mode,
            current_index=view.current_index, count=len(images),
            strip_width=strip_width,
        )
        if not items:
            return
        y_top, band_h = filmstrip_band(view.height(), ITEM_HEIGHT, BAND_VPAD)
        painter.fillRect(0, int(y_top), int(strip_width), int(band_h),
                         QColor(*_FILMSTRIP_BAND_RGBA))
        for index, x_left in items:
            self._draw_filmstrip_item(painter, images[index], x_left,
                                      y_top + BAND_VPAD, index == view.current_index)

    def _draw_filmstrip_item(self, painter: QPainter, path: str,  # pragma: no cover
                             x_left: float, item_y: float, is_current: bool) -> None:
        pixmap = self._filmstrip_pixmap(path)
        if pixmap is not None:
            fx, fy, fw, fh = fit_rect_centered(
                pixmap.width(), pixmap.height(), x_left, item_y,
                ITEM_WIDTH, ITEM_HEIGHT,
            )
            painter.drawPixmap(int(fx), int(fy), int(fw), int(fh), pixmap)
        else:
            painter.fillRect(int(x_left), int(item_y), ITEM_WIDTH, ITEM_HEIGHT,
                             QColor(*_FILMSTRIP_PLACEHOLDER_RGBA))
        if is_current:
            pen = QPen(QColor(*_FILMSTRIP_HIGHLIGHT_RGBA))
            pen.setWidth(_FILMSTRIP_BORDER_WIDTH)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x_left), int(item_y), ITEM_WIDTH, ITEM_HEIGHT)

    def _filmstrip_pixmap(self, path: str):  # pragma: no cover - GL paint
        """Cached QPixmap for *path*, built lazily from the tile thumbnail cache."""
        cache = self.view._filmstrip_thumb_cache
        if path in cache:
            return cache[path]
        arr = self.view.tile_cache.get(path)
        if arr is None:
            return None
        pixmap = _rgba_to_pixmap(arr)
        cache[path] = pixmap
        return pixmap

    def draw_loupe(self, painter: QPainter):  # pragma: no cover - GL paint
        """Cursor-following magnifier showing image pixels at higher zoom."""
        view = self.view
        base = view.deep_zoom.levels[0]
        img_h, img_w = base.shape[:2]
        cx, cy = view._hover_image_xy
        if not (0 <= cx < img_w and 0 <= cy < img_h):
            return
        sample = max(1, round(LOUPE_BOX_PX / view._loupe_magnification))
        left, top, right, bottom = loupe_source_rect(cx, cy, sample, sample,
                                                      img_w, img_h)
        crop = base[top:bottom, left:right]
        if crop.size == 0:
            return
        screen_x = int(cx * view.zoom + view.dz_offset_x)
        screen_y = int(cy * view.zoom + view.dz_offset_y)
        box_x, box_y = place_hud_box(screen_x, screen_y, _LOUPE_CURSOR_GAP,
                                     LOUPE_BOX_PX, LOUPE_BOX_PX,
                                     view.width(), view.height())
        painter.drawPixmap(box_x, box_y, LOUPE_BOX_PX, LOUPE_BOX_PX,
                           _rgba_to_pixmap(crop))
        self._draw_loupe_frame(painter, box_x, box_y)

    def _draw_loupe_frame(self, painter: QPainter,  # pragma: no cover - GL paint
                          box_x: int, box_y: int) -> None:
        pen = QPen(QColor(*_LOUPE_BORDER_RGBA))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(box_x, box_y, LOUPE_BOX_PX, LOUPE_BOX_PX)
        mid = LOUPE_BOX_PX // 2
        painter.setPen(QColor(*_LOUPE_CROSSHAIR_RGBA))
        painter.drawLine(box_x + mid, box_y, box_x + mid, box_y + LOUPE_BOX_PX)
        painter.drawLine(box_x, box_y + mid, box_x + LOUPE_BOX_PX, box_y + mid)

    def draw_zoom_band(self, painter: QPainter):  # pragma: no cover - GL paint
        """Draw the rubber-band rectangle while the user frames a zoom region."""
        view = self.view
        start, end = view._zoom_band_start, view._zoom_band_end
        left, top = min(start.x(), end.x()), min(start.y(), end.y())
        width, height = abs(end.x() - start.x()), abs(end.y() - start.y())
        painter.fillRect(int(left), int(top), int(width), int(height),
                         QColor(*_ZOOM_BAND_FILL_RGBA))
        pen = QPen(QColor(*_ZOOM_BAND_BORDER_RGBA))
        pen.setWidth(_ZOOM_BAND_BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(left), int(top), int(width), int(height))

    def draw_loading_preview(self, painter: QPainter) -> None:  # pragma: no cover
        """Background low-res preview shown while the full image streams in."""
        view = self.view
        pixmap = self._filmstrip_pixmap(view._deep_zoom_loading)
        if pixmap is None:
            return
        fx, fy, fw, fh = fit_rect_centered(
            pixmap.width(), pixmap.height(), 0, 0, view.width(), view.height(),
        )
        painter.drawPixmap(int(fx), int(fy), int(fw), int(fh), pixmap)

    def draw_loading_pill(self, painter: QPainter) -> None:  # pragma: no cover
        view = self.view
        lang = view.main_window.language_wrapper.language_word_dict
        text = lang.get("status_loading_image", "Loading image...")
        font = QFont(_FONT_SEGOE_UI)
        font.setPixelSize(14)
        painter.setFont(font)
        fm = painter.fontMetrics()
        pad_x, pad_y = 16, 8
        box_w = fm.horizontalAdvance(text) + pad_x * 2
        box_h = fm.height() + pad_y * 2
        x = (view.width() - box_w) // 2
        y = (view.height() - box_h) // 2
        painter.fillRect(x, y, box_w, box_h, QColor(*_LOADING_PILL_RGBA))
        painter.setPen(QColor(235, 235, 235))
        painter.drawText(x + pad_x, y + pad_y + fm.ascent(), text)


def _paint_play_badge(painter, badge) -> None:  # pragma: no cover - GL paint
    """Draw a translucent disc + white play triangle for a video badge."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(*_VIDEO_BADGE_DISC_RGBA))
    painter.drawEllipse(QPointF(badge.cx, badge.cy), badge.radius, badge.radius)
    painter.setBrush(QColor(*_VIDEO_BADGE_TRI_RGBA))
    painter.drawPolygon(QPolygonF([QPointF(vx, vy) for vx, vy in badge.triangle]))


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


def _paint_bookmark_badge(painter, y0, x1, path: str) -> None:  # pragma: no cover - GL paint
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
