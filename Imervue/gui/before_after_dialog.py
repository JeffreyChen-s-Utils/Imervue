"""Before / After split-slider comparison for the non-destructive recipe.

Loads the current image twice — once with no recipe ("before") and once with
the saved recipe applied ("after") — and shows them in one view split by a
draggable vertical divider, so the user can judge a develop edit in place.

The split geometry (divider position, hit-testing, aspect-fit rect) is kept in
module-level pure functions so it is unit-testable without a display; the
``QWidget`` is a thin renderer over them.
"""
from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

logger = logging.getLogger("Imervue.gui.before_after_dialog")

_HANDLE_TOLERANCE_PX = 14
_DIVIDER_WIDTH_PX = 2


def clamp_fraction(fraction: float) -> float:
    """Clamp a divider position to the closed ``[0, 1]`` range."""
    return max(0.0, min(1.0, float(fraction)))


def divider_x(fraction: float, width: int) -> int:
    """Pixel x of the divider within a strip of *width* px."""
    return int(round(clamp_fraction(fraction) * max(0, width)))


def fraction_from_x(x: float, width: int) -> float:
    """Divider fraction for a pixel *x* within *width*; 0 for an empty strip."""
    if width <= 0:
        return 0.0
    return clamp_fraction(x / width)


def near_divider(x: float, fraction: float, width: int,
                 tolerance: int = _HANDLE_TOLERANCE_PX) -> bool:
    """True when *x* is within *tolerance* px of the divider — the grab zone."""
    return abs(x - divider_x(fraction, width)) <= tolerance


def fit_rect(img_w: int, img_h: int, area_w: int, area_h: int) -> tuple[int, int, int, int]:
    """Aspect-preserving, centred ``(x, y, w, h)`` for an image inside an area.

    Degenerate (zero) image or area dimensions collapse to a zero-size rect at
    the origin rather than dividing by zero.
    """
    if img_w <= 0 or img_h <= 0 or area_w <= 0 or area_h <= 0:
        return 0, 0, 0, 0
    scale = min(area_w / img_w, area_h / img_h)
    w = max(1, int(round(img_w * scale)))
    h = max(1, int(round(img_h * scale)))
    return (area_w - w) // 2, (area_h - h) // 2, w, h


class BeforeAfterView(QWidget):
    """Renders *before* on the left of a draggable divider and *after* on the
    right; both images are scaled to a shared aspect-fit rect so they register
    pixel-for-pixel across the split."""

    def __init__(self, before: QImage, after: QImage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._before = before
        self._after = after
        self._fraction = 0.5
        self._dragging = False
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)

    def fraction(self) -> float:
        return self._fraction

    def _display_rect(self) -> tuple[int, int, int, int]:
        return fit_rect(max(1, self._after.width()), max(1, self._after.height()),
                        self.width(), self.height())

    def set_divider_from_widget_x(self, x: float) -> None:
        """Move the divider to widget-space *x* (clamped to the image rect)."""
        rx, _, rw, _ = self._display_rect()
        self._fraction = fraction_from_x(x - rx, rw)
        self.update()

    def mousePressEvent(self, event):  # pragma: no cover - Qt event glue
        rx, _, rw, _ = self._display_rect()
        if near_divider(event.position().x() - rx, self._fraction, rw):
            self._dragging = True
        self.set_divider_from_widget_x(event.position().x())

    def mouseMoveEvent(self, event):  # pragma: no cover - Qt event glue
        if self._dragging:
            self.set_divider_from_widget_x(event.position().x())

    def mouseReleaseEvent(self, event):  # pragma: no cover - Qt event glue
        self._dragging = False

    def paintEvent(self, event):  # pragma: no cover - QPainter rendering
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 24, 24))
        rx, ry, rw, rh = self._display_rect()
        if rw == 0 or rh == 0:
            return
        dest = QRect(rx, ry, rw, rh)
        div = divider_x(self._fraction, rw)
        painter.drawImage(dest, self._after)
        painter.save()
        painter.setClipRect(QRect(rx, ry, div, rh))
        painter.drawImage(dest, self._before)
        painter.restore()
        self._paint_divider(painter, rx, ry, rh, div)

    def _paint_divider(self, painter, rx, ry, rh, div):  # pragma: no cover - QPainter
        painter.setPen(QPen(QColor(255, 255, 255, 230), _DIVIDER_WIDTH_PX))
        painter.drawLine(rx + div, ry, rx + div, ry + rh)
        painter.setPen(QColor(235, 235, 235))
        painter.drawText(rx + 8, ry + 20, "Before")
        painter.drawText(rx + div + 8, ry + 20, "After")


class BeforeAfterDialog(QDialog):
    """Modal split-slider window comparing a *before* and *after* QImage."""

    def __init__(self, before: QImage, after: QImage, title: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 640)
        self._view = BeforeAfterView(before, after, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)


def rgba_to_qimage(arr: np.ndarray) -> QImage:
    """Convert an HxWx4 uint8 RGBA array to an owned (copied) QImage."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(f"expected HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}")
    h, w = arr.shape[:2]
    contiguous = np.ascontiguousarray(arr)
    return QImage(contiguous.tobytes(), w, h, w * 4,
                  QImage.Format.Format_RGBA8888).copy()


def open_before_after_dialog(viewer) -> None:
    """Open the Before/After dialog for the viewer's current deep-zoom image."""
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    path = str(images[idx])
    try:
        before, after = _load_pair(path)
    except (OSError, ValueError):
        logger.exception("Before/After failed to load %s", path)
        return
    parent = getattr(viewer, "main_window", viewer)
    from pathlib import Path
    BeforeAfterDialog(before, after, f"Before / After — {Path(path).name}",
                      parent).exec()


def _load_pair(path: str) -> tuple[QImage, QImage]:
    """Load (before=no recipe, after=saved recipe) as QImages."""
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    from Imervue.image.recipe_store import recipe_store
    before = rgba_to_qimage(load_image_file(path, recipe=None))
    after = rgba_to_qimage(load_image_file(path, recipe=recipe_store.get_for_path(path)))
    return before, after
