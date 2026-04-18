"""
縮圖懸停預覽彈窗
Hover preview popup — a frameless tooltip-like window that shows a larger
view of whichever thumbnail the cursor is resting on.

Triggered by the viewer / list-view when the cursor stays on a tile for
``HOVER_DELAY_MS``. Cancel conditions: mouse leaves, moves to a different
tile, or the user clicks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QTimer, QPoint, QSize, Signal
from PySide6.QtGui import QPixmap, QImage, QGuiApplication, QFont
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QApplication

HOVER_DELAY_MS = 500
PREVIEW_MAX_EDGE = 512


class HoverPreviewPopup(QWidget):
    """Frameless top-level that shows a scaled preview + filename caption."""

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(
            "HoverPreviewPopup {"
            " background-color: #1e1e1e; border: 1px solid #444;"
            "}"
            "QLabel { color: #ddd; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(64, 64)
        layout.addWidget(self._image_label)

        self._caption = QLabel("")
        font = QFont("Segoe UI")
        font.setPixelSize(11)
        self._caption.setFont(font)
        self._caption.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._caption.setWordWrap(False)
        layout.addWidget(self._caption)

    def show_for(self, path: str, anchor_global: QPoint) -> None:
        """Load ``path``, build the caption, and position near ``anchor_global``.

        The popup dodges the cursor so the user can keep browsing — it
        appears on the right of the anchor, or the left if that would
        cross the screen edge.
        """
        pm = _load_preview(path)
        if pm is None:
            self.hide()
            return

        self._image_label.setPixmap(pm)
        self._image_label.setFixedSize(pm.size())

        caption = self._build_caption(path, pm)
        self._caption.setText(caption)
        self.adjustSize()

        self.move(_clamp_to_screen(anchor_global + QPoint(20, 20), self.size()))
        self.show()
        self.raise_()

    def _build_caption(self, path: str, pm: QPixmap) -> str:
        name = Path(path).name
        try:
            stat = os.stat(path)
            size = stat.st_size
        except OSError:
            size = 0
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        elif size > 0:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = "—"
        return f"{name}   \u00B7   {pm.width()}\u00D7{pm.height()}   \u00B7   {size_str}"


def _load_preview(path: str, max_edge: int = PREVIEW_MAX_EDGE) -> QPixmap | None:
    """Load a file and downscale to ``max_edge`` on the long side.

    Falls back to whatever PIL can open; returns None on failure so the
    popup stays hidden rather than showing a broken preview.
    """
    try:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            w, h = im.size
            long_edge = max(w, h)
            if long_edge > max_edge:
                scale = max_edge / long_edge
                im = im.resize(
                    (int(w * scale), int(h * scale)),
                    Image.Resampling.LANCZOS,
                )
            data = im.tobytes("raw", "RGBA")
            qimg = QImage(
                data, im.width, im.height, QImage.Format.Format_RGBA8888
            ).copy()
            return QPixmap.fromImage(qimg)
    except Exception:
        return None


def _clamp_to_screen(pos: QPoint, size: QSize) -> QPoint:
    """Keep the popup fully on-screen — flip to other side if it overflows."""
    screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
    if screen is None:
        return pos
    avail = screen.availableGeometry()
    x, y = pos.x(), pos.y()
    if x + size.width() > avail.right():
        x = avail.right() - size.width()
    if y + size.height() > avail.bottom():
        y = avail.bottom() - size.height()
    if x < avail.left():
        x = avail.left()
    if y < avail.top():
        y = avail.top()
    return QPoint(x, y)


class HoverPreviewController:
    """Orchestrates the delay timer + popup for a single host widget.

    One controller per host (the tile grid viewer owns one). Calling
    ``arm(path, pos)`` schedules a show after the delay; ``disarm()``
    cancels/hides. ``move(path, pos)`` is cheap and used while the cursor
    is still inside the same widget.
    """

    def __init__(self):
        self._popup = HoverPreviewPopup()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)
        self._pending_path: str | None = None
        self._pending_pos: QPoint | None = None
        self._current_path: str | None = None

    def arm(self, path: str, global_pos: QPoint) -> None:
        """Schedule a preview if ``path`` differs from the one already showing."""
        if path == self._current_path and self._popup.isVisible():
            # Same tile already showing — just track cursor for later moves
            self._pending_pos = global_pos
            return
        if path == self._pending_path and self._timer.isActive():
            self._pending_pos = global_pos  # keep latest anchor
            return
        self._pending_path = path
        self._pending_pos = global_pos
        self._timer.start(HOVER_DELAY_MS)
        self._current_path = None

    def disarm(self) -> None:
        """Cancel pending timer and hide any visible popup."""
        self._timer.stop()
        self._pending_path = None
        self._pending_pos = None
        self._current_path = None
        if self._popup.isVisible():
            self._popup.hide()

    def _on_timer(self) -> None:
        if not self._pending_path or self._pending_pos is None:
            return
        self._current_path = self._pending_path
        self._popup.show_for(self._pending_path, self._pending_pos)
