"""GUI editor for :class:`Imervue.paint.pressure_curve.PressureCurve`.

A small modal dialog wrapping a custom QWidget canvas:

* Drag a control point with the left mouse button to reshape the
  curve.
* Right-click a control point to remove it (the endpoints at x=0 and
  x=1 cannot be removed — the curve must cover the full input range).
* Left-click on empty space to insert a new control point at the
  click location.

Three preset buttons (Linear / Soft / Hard) drop a starter curve into
the editor for the artists who want a baseline before fine-tuning.
The dialog returns the edited :class:`PressureCurve` on accept; on
reject it returns the original.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.pressure_curve import PressureCurve

# Drag radius — clicking within this many pixels of a control point
# selects that point for dragging instead of inserting a new one.
_DRAG_RADIUS_PX = 10
# Minimum spacing along the input axis so two points never collide.
_MIN_INPUT_SPACING = 0.005


class PressureCurveEditor(QWidget):
    """Custom widget — draws the curve and routes mouse to control points."""

    points_changed = Signal()

    def __init__(self, curve: PressureCurve | None = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 180)
        self._points: list[tuple[float, float]] = list(
            (curve or PressureCurve()).points,
        )
        self._dragging: int | None = None

    # ---- public ----------------------------------------------------------

    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def set_points(self, points) -> None:
        self._points = sorted(
            (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
            for x, y in points
        )
        self.update()
        self.points_changed.emit()

    def to_curve(self) -> PressureCurve:
        return PressureCurve(points=tuple(self._points))

    # ---- painting --------------------------------------------------------

    def paintEvent(self, event) -> None:  # pragma: no cover - Qt UI
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect())
            painter.fillRect(rect, QColor("#222"))
            self._paint_grid(painter, rect)
            self._paint_curve(painter, rect)
            self._paint_handles(painter, rect)
        finally:
            painter.end()

    def _paint_grid(self, painter, rect):  # pragma: no cover - Qt UI
        pen = QPen(QColor("#333"))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 5):
            x = rect.x() + rect.width() * i / 5.0
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            y = rect.y() + rect.height() * i / 5.0
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _paint_curve(self, painter, rect):  # pragma: no cover - Qt UI
        if len(self._points) < 2:
            return
        pen = QPen(QColor("#5dd"))
        pen.setWidth(2)
        painter.setPen(pen)
        last = self._curve_to_screen(self._points[0], rect)
        for pt in self._points[1:]:
            current = self._curve_to_screen(pt, rect)
            painter.drawLine(last, current)
            last = current

    def _paint_handles(self, painter, rect):  # pragma: no cover - Qt UI
        pen = QPen(QColor("#fff"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QColor("#5dd"))
        for pt in self._points:
            screen = self._curve_to_screen(pt, rect)
            painter.drawEllipse(screen, 4.0, 4.0)

    # ---- coordinate helpers (testable) ----------------------------------

    def _curve_to_screen(self, point, rect) -> QPointF:
        x, y = point
        return QPointF(
            rect.x() + x * rect.width(),
            rect.y() + (1.0 - y) * rect.height(),
        )

    def _screen_to_curve(self, screen_pos, rect) -> tuple[float, float]:
        x_norm = (screen_pos.x() - rect.x()) / max(1.0, rect.width())
        y_norm = 1.0 - (screen_pos.y() - rect.y()) / max(1.0, rect.height())
        return (
            max(0.0, min(1.0, x_norm)),
            max(0.0, min(1.0, y_norm)),
        )

    # ---- input -----------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        rect = QRectF(self.rect())
        index = self._hit_point(event.position(), rect)
        if event.button() == Qt.MouseButton.RightButton:
            if index is not None and 0 < index < len(self._points) - 1:
                del self._points[index]
                self.update()
                self.points_changed.emit()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if index is not None:
                self._dragging = index
                return
            # Insert a new point.
            new_point = self._screen_to_curve(event.position(), rect)
            self._insert_point(new_point)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        if self._dragging is None:
            return
        rect = QRectF(self.rect())
        x, y = self._screen_to_curve(event.position(), rect)
        self._move_point(self._dragging, x, y)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # pragma: no cover
        self._dragging = None

    # ---- mutation helpers (testable) ------------------------------------

    def _hit_point(self, screen_pos, rect) -> int | None:
        for index, pt in enumerate(self._points):
            handle = self._curve_to_screen(pt, rect)
            dx = handle.x() - screen_pos.x()
            dy = handle.y() - screen_pos.y()
            if dx * dx + dy * dy <= _DRAG_RADIUS_PX * _DRAG_RADIUS_PX:
                return index
        return None

    def _insert_point(self, point: tuple[float, float]) -> None:
        x, y = point
        # Clamp into a valid slot — endpoints are immutable so the new
        # point sits strictly between them.
        x = max(_MIN_INPUT_SPACING, min(1.0 - _MIN_INPUT_SPACING, x))
        y = max(0.0, min(1.0, y))
        # Find the insert position so the list stays sorted by x.
        for i in range(1, len(self._points)):
            if self._points[i][0] > x:
                self._points.insert(i, (x, y))
                self.update()
                self.points_changed.emit()
                return
        # Should be unreachable because endpoints are at x=0 and x=1.

    def _move_point(self, index: int, x: float, y: float) -> None:
        if not 0 <= index < len(self._points):
            return
        if index == 0:
            x = 0.0
        elif index == len(self._points) - 1:
            x = 1.0
        else:
            lo = self._points[index - 1][0] + _MIN_INPUT_SPACING
            hi = self._points[index + 1][0] - _MIN_INPUT_SPACING
            x = max(lo, min(hi, x))
        y = max(0.0, min(1.0, y))
        self._points[index] = (x, y)
        self.update()
        self.points_changed.emit()


# ---------------------------------------------------------------------------
# Dialog wrapper
# ---------------------------------------------------------------------------


_PRESET_LINEAR = ((0.0, 0.0), (1.0, 1.0))
_PRESET_SOFT = ((0.0, 0.0), (0.5, 0.25), (1.0, 1.0))
_PRESET_HARD = ((0.0, 0.0), (0.5, 0.75), (1.0, 1.0))


class PressureCurveDialog(QDialog):
    """Modal dialog that returns a :class:`PressureCurve` on accept."""

    def __init__(self, curve: PressureCurve | None = None, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_pressure_curve_title", "Pressure Curve"),
        )
        layout = QVBoxLayout(self)

        self._editor = PressureCurveEditor(curve=curve, parent=self)
        layout.addWidget(self._editor, stretch=1)

        presets_row = QHBoxLayout()
        for key, fallback, points in (
            ("paint_pressure_curve_linear", "Linear", _PRESET_LINEAR),
            ("paint_pressure_curve_soft", "Soft", _PRESET_SOFT),
            ("paint_pressure_curve_hard", "Hard", _PRESET_HARD),
        ):
            btn = QPushButton(lang.get(key, fallback))
            btn.clicked.connect(
                lambda *_, p=points: self._editor.set_points(p),
            )
            presets_row.addWidget(btn)
        presets_row.addStretch(1)
        layout.addLayout(presets_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def curve(self) -> PressureCurve:
        return self._editor.to_curve()

    def editor(self) -> PressureCurveEditor:
        return self._editor
