"""
Tone curve editor dialog.

A light-weight draggable-points curve editor. Points are shown over a
histogram preview of the current image; dragging moves them, right-click
removes, left-click on empty space adds. Four tabs switch between the
master RGB curve and per-channel R / G / B curves.

Committing calls back into ``recipe_store`` so the curve applies
non-destructively on the next render.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.image.recipe import Recipe
from Imervue.image.recipe_store import recipe_store
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.tone_curve_dialog")

_CURVE_CHOICES = [
    ("tone_curve_rgb", "curve_channel_rgb", "RGB"),
    ("tone_curve_r", "curve_channel_r", "Red"),
    ("tone_curve_g", "curve_channel_g", "Green"),
    ("tone_curve_b", "curve_channel_b", "Blue"),
]


class _CurveCanvas(QWidget):
    """Widget that shows a single curve with draggable control points."""

    points_changed = Signal(list)  # list[tuple[float, float]]

    _HANDLE_RADIUS = 6
    _MIN_SIZE = 260

    def __init__(self, points: list[tuple[float, float]], parent=None):
        super().__init__(parent)
        self.setMinimumSize(self._MIN_SIZE, self._MIN_SIZE)
        self.setMouseTracking(True)
        self._points: list[list[float]] = [list(p) for p in points] or [
            [0.0, 0.0], [1.0, 1.0],
        ]
        self._drag_idx: int | None = None
        self._stroke_color = QColor(230, 230, 230)

    def points(self) -> list[tuple[float, float]]:
        return [(float(x), float(y)) for x, y in self._points]

    def set_points(self, points: list[tuple[float, float]]) -> None:
        self._points = [list(p) for p in points] or [[0.0, 0.0], [1.0, 1.0]]
        self.update()

    # ------------------------------------------------------------------
    # Coordinate helpers — canvas Y is inverted relative to curve space.
    # ------------------------------------------------------------------

    def _to_canvas(self, x: float, y: float) -> QPointF:
        w = self.width() - 1
        h = self.height() - 1
        return QPointF(x * w, (1.0 - y) * h)

    def _from_canvas(self, px: float, py: float) -> tuple[float, float]:
        w = max(1, self.width() - 1)
        h = max(1, self.height() - 1)
        return (
            max(0.0, min(1.0, px / w)),
            max(0.0, min(1.0, 1.0 - py / h)),
        )

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):  # noqa: N802 - Qt override
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        self._draw_grid(painter)
        self._draw_curve(painter)
        self._draw_handles(painter)

    def _draw_grid(self, painter: QPainter) -> None:
        pen = QPen(QColor(70, 70, 70))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 4):
            t = i / 4.0
            p1 = self._to_canvas(t, 0.0)
            p2 = self._to_canvas(t, 1.0)
            painter.drawLine(p1, p2)
            p3 = self._to_canvas(0.0, t)
            p4 = self._to_canvas(1.0, t)
            painter.drawLine(p3, p4)

    def _draw_curve(self, painter: QPainter) -> None:
        from Imervue.image.tone_curve import build_lut
        pen = QPen(self._stroke_color)
        pen.setWidth(2)
        painter.setPen(pen)
        lut = build_lut([tuple(p) for p in self._points])
        w = self.width() - 1
        prev = None
        for i in range(self.width()):
            t = i / max(1, w)
            idx = min(255, int(t * 255))
            y = lut[idx] / 255.0
            pt = self._to_canvas(t, y)
            if prev is not None:
                painter.drawLine(prev, pt)
            prev = pt

    def _draw_handles(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QColor(80, 160, 240))
        for x, y in self._points:
            c = self._to_canvas(x, y)
            painter.drawEllipse(c, self._HANDLE_RADIUS, self._HANDLE_RADIUS)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _hit_test(self, pos: QPointF) -> int | None:
        for i, (x, y) in enumerate(self._points):
            if (self._to_canvas(x, y) - pos).manhattanLength() < self._HANDLE_RADIUS * 2:
                return i
        return None

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        pos = QPointF(event.position())
        hit = self._hit_test(pos)
        if event.button() == Qt.MouseButton.RightButton:
            if hit is not None and len(self._points) > 2:
                self._points.pop(hit)
                self.points_changed.emit(self.points())
                self.update()
            return
        if hit is not None:
            self._drag_idx = hit
            return
        # Add a new point at the click location.
        x, y = self._from_canvas(pos.x(), pos.y())
        self._points.append([x, y])
        self._points.sort(key=lambda p: p[0])
        self._drag_idx = next(
            (i for i, p in enumerate(self._points) if p[0] == x and p[1] == y),
            None,
        )
        self.points_changed.emit(self.points())
        self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        if self._drag_idx is None:
            return
        pos = QPointF(event.position())
        x, y = self._from_canvas(pos.x(), pos.y())
        self._points[self._drag_idx][0] = x
        self._points[self._drag_idx][1] = y
        self._points.sort(key=lambda p: p[0])
        self._drag_idx = next(
            (i for i, p in enumerate(self._points) if p[0] == x and p[1] == y),
            self._drag_idx,
        )
        self.points_changed.emit(self.points())
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        _ = event
        self._drag_idx = None


class ToneCurveDialog(QDialog):
    """Modal dialog that lets the user edit the four tone curves."""

    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("tone_curve_title", "Tone Curve"))

        self._recipe = recipe_store.get_for_path(path) or Recipe()
        self._curves: dict[str, list[tuple[float, float]]] = {
            field_name: list(getattr(self._recipe, field_name))
            for field_name, _, _ in _CURVE_CHOICES
        }

        self._channel_combo = QComboBox()
        for _field, key, fallback in _CURVE_CHOICES:
            self._channel_combo.addItem(lang.get(key, fallback))
        self._channel_combo.currentIndexChanged.connect(self._reload_canvas)

        self._canvas = _CurveCanvas(self._curves["tone_curve_rgb"])
        self._canvas.points_changed.connect(self._on_points_changed)

        self._reset_btn = QPushButton(lang.get("tone_curve_reset", "Reset Channel"))
        self._reset_btn.clicked.connect(self._reset_channel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)

        top = QHBoxLayout()
        top.addWidget(QLabel(lang.get("tone_curve_channel_label", "Channel:")))
        top.addWidget(self._channel_combo, 1)
        top.addWidget(self._reset_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(QLabel(
            lang.get(
                "tone_curve_hint",
                "Left-click empty area to add a point; drag to move; right-click to delete.",
            ),
        ))
        layout.addWidget(buttons)

    def _active_field(self) -> str:
        return _CURVE_CHOICES[self._channel_combo.currentIndex()][0]

    def _reload_canvas(self) -> None:
        self._canvas.set_points(self._curves[self._active_field()])

    def _on_points_changed(self, points: list[tuple[float, float]]) -> None:
        self._curves[self._active_field()] = list(points)

    def _reset_channel(self) -> None:
        self._curves[self._active_field()] = [(0.0, 0.0), (1.0, 1.0)]
        self._reload_canvas()

    def _commit(self) -> None:
        old = self._recipe
        new = Recipe(**{
            **{f.name: getattr(old, f.name) for f in old.__dataclass_fields__.values()},
        })
        for field_name in self._curves:
            setattr(new, field_name, list(self._curves[field_name]))
        recipe_store.set_for_path(self._path, new)
        hook = getattr(self._viewer, "reload_current_image_with_recipe", None)
        if callable(hook):
            hook(self._path)
        self.accept()


def open_tone_curve(viewer: "GPUImageView") -> None:
    """Open the tone curve editor for the currently displayed image."""
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    dialog = ToneCurveDialog(viewer, str(path))
    dialog.exec()
