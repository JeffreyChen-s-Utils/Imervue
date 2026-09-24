"""Per-tile badges painted over the thumbnail wall.

Colour-label strip, favourite heart, bookmark star, star rating, RAW+JPEG
stack count, modified-date chip, and the video play disc (also used on the
single-image view). Each function paints with the given ``QPainter`` in widget
coordinates and draws nothing when its condition does not hold.
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPolygonF

_VIDEO_BADGE_DISC_RGBA = (0, 0, 0, 150)
_VIDEO_BADGE_TRI_RGBA = (255, 255, 255, 235)


def paint_play_badge(painter, badge) -> None:
    """Draw a translucent disc + white play triangle for a video badge."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(*_VIDEO_BADGE_DISC_RGBA))
    painter.drawEllipse(QPointF(badge.cx, badge.cy), badge.radius, badge.radius)
    painter.setBrush(QColor(*_VIDEO_BADGE_TRI_RGBA))
    painter.drawPolygon(QPolygonF([QPointF(vx, vy) for vx, vy in badge.triangle]))


def paint_color_strip(painter, x0, y0, y1, color_name) -> None:
    """Left-edge 6 px colour-label strip; skipped when no label is set."""
    from Imervue.user_settings.color_labels import COLOR_RGB
    if not color_name or color_name not in COLOR_RGB:
        return
    r, g, b = COLOR_RGB[color_name]
    painter.fillRect(int(x0), int(y0), 6, int(y1 - y0), QColor(r, g, b, 230))


def paint_favorite_badge(painter, x0, y0, is_fav: bool,
                          color_name) -> None:
    if not is_fav:
        return
    offset = 10 if color_name else 4
    painter.fillRect(int(x0 + offset), int(y0 + 4), 18, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 90, 120))
    painter.drawText(int(x0 + offset + 2), int(y0 + 18), "♥")


def paint_bookmark_badge(painter, y0, x1, path: str) -> None:
    from Imervue.user_settings.bookmark import is_bookmarked
    if not is_bookmarked(path):
        return
    painter.fillRect(int(x1 - 22), int(y0 + 4), 18, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 210, 80))
    painter.drawText(int(x1 - 20), int(y0 + 18), "★")


def paint_rating_badge(painter, x0, y1, rating: int) -> None:
    if not rating or rating <= 0:
        return
    badge_text = "★" * int(rating)
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(badge_text)
    painter.fillRect(int(x0 + 4), int(y1 - 20), tw + 8, 18, QColor(0, 0, 0, 140))
    painter.setPen(QColor(255, 210, 80))
    painter.drawText(int(x0 + 8), int(y1 - 6), badge_text)


def paint_stack_badge(painter, x1, y1, count: int) -> None:
    if count <= 1:
        return
    text = f"x{count}"
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    painter.fillRect(int(x1 - tw - 14), int(y1 - 20), tw + 10, 18, QColor(20, 80, 110, 190))
    painter.setPen(QColor(230, 250, 255))
    painter.drawText(int(x1 - tw - 9), int(y1 - 6), text)


def mtime_date_label(path: str) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
    except OSError:
        return ""


def paint_date_chip(painter, x0, y0, text: str) -> None:
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    x = int(x0 + 4)
    y = int(y0 + 4)
    painter.fillRect(x, y, tw + 12, 18, QColor(0, 0, 0, 165))
    painter.setPen(QColor(210, 230, 255))
    painter.drawText(x + 6, y + 13, text)
