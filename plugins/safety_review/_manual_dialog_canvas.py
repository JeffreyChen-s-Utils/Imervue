"""Drawing canvas of the safety_review manual censor editor.

``_ManualCanvas`` holds the image and the hand-drawn censor boxes (with one
class id per box) and paints them; mouse / keyboard editing comes from
``_ManualCanvasInputMixin`` in :mod:`_manual_dialog_input`. All geometry is
delegated to the pure :mod:`_manual` helpers. A plain ``QWidget`` (no
``QOpenGLWidget``), so it needs no headless-CI skip marker.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from safety_review._manual import (
    clamp_region,
    fit_scale,
    is_valid_region,
    to_display_rect,
)
from safety_review._manual_dialog_input import _ManualCanvasInputMixin

_MAX_CANVAS_W = 1100
_MAX_CANVAS_H = 720


class _ManualCanvas(_ManualCanvasInputMixin, QWidget):
    """Image + hand-drawn censor boxes; delegates geometry to :mod:`_manual`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scale = 1.0
        self._regions: list = []          # image-space (x1,y1,x2,y2)
        self._classes: list = []          # class id per region (parallel)
        self._current_class = 0           # class assigned to newly drawn boxes
        self._selected = -1
        self._drawing = False
        self._moving = False
        self._draw_start = None           # display-space
        self._draw_cur = None
        self._move_last = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- state -------------------------------------------------------

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._scale = fit_scale(pixmap.width(), pixmap.height(),
                                _MAX_CANVAS_W, _MAX_CANVAS_H)
        self.setFixedSize(max(1, int(pixmap.width() * self._scale)),
                          max(1, int(pixmap.height() * self._scale)))
        self.update()

    def image_size(self):
        return (self._pixmap.width(), self._pixmap.height()) if self._pixmap else (0, 0)

    def regions(self):
        return list(self._regions)

    def labeled_regions(self):
        """[(box, class_id), …] for training-label export."""
        return list(zip(self._regions, self._classes, strict=False))

    def set_current_class(self, cls: int):
        """Class assigned to boxes drawn from now on; re-classes the selection."""
        self._current_class = cls
        if 0 <= self._selected < len(self._classes):
            self._classes[self._selected] = cls
            self.update()

    def selected_class(self):
        if 0 <= self._selected < len(self._classes):
            return self._classes[self._selected]
        return None

    def add_regions(self, boxes, classes=None) -> int:
        """Append detected *boxes* (image coords), clamped and speck-filtered.

        *classes* (aligned with *boxes*) sets each box's class; without it the
        current class is used.
        """
        iw, ih = self.image_size()
        added = 0
        for i, box in enumerate(boxes):
            region = clamp_region(tuple(box), iw, ih)
            if is_valid_region(region):
                self._regions.append(region)
                self._classes.append(
                    classes[i] if classes is not None else self._current_class)
                added += 1
        self.update()
        return added

    def clear_regions(self):
        self._regions = []
        self._classes = []
        self._selected = -1
        self.update()

    def _remove_region(self, idx: int):
        if 0 <= idx < len(self._regions):
            self._regions.pop(idx)
            if idx < len(self._classes):
                self._classes.pop(idx)

    # -- painting ----------------------------------------------------

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        if self._pixmap is not None:
            painter.drawPixmap(self.rect(), self._pixmap)
        for i, region in enumerate(self._regions):
            selected = i == self._selected
            x, y, w, h = to_display_rect(region, self._scale)
            painter.fillRect(x, y, w, h,
                             QColor(0, 120, 255, 90) if selected
                             else QColor(255, 0, 0, 70))
            painter.setPen(QPen(QColor(0, 120, 255) if selected
                                else QColor(255, 0, 0), 2))
            painter.drawRect(x, y, w, h)
        if self._drawing and self._draw_start and self._draw_cur:
            x0, y0 = self._draw_start
            x1, y1 = self._draw_cur
            painter.setPen(QPen(QColor(255, 200, 0), 2))
            painter.drawRect(int(min(x0, x1)), int(min(y0, y1)),
                             int(abs(x1 - x0)), int(abs(y1 - y0)))
