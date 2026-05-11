"""Motion timeline editor — graph view of one :class:`MotionTrack`'s
curve with draggable endpoint and bezier-handle markers.

Far from Cubism Editor's full timeline, but covers the common workflow:
pick a track, see the curve, drag a point to tweak it. The widget is
self-contained QGraphicsView + QGraphicsItems so the workspace can
either embed it inline or wrap it in a dialog (we ship the dialog
form).

Pure-Qt — no GL — so the headless test suite can drive it under
``qapp`` and assert that a dragged handle ends up writing to the
correct segment field.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from puppet.document import MotionTrack

if TYPE_CHECKING:
    from puppet.document import Motion


# Scene units are pixels at zoom = 1; the view auto-fits on first show.
_SCENE_WIDTH: float = 800.0
_SCENE_HEIGHT: float = 240.0
_MARGIN: float = 20.0
_ENDPOINT_RADIUS: float = 5.0
_CONTROL_RADIUS: float = 3.5


class MotionTimelineWidget(QGraphicsView):
    """Graph view of one :class:`MotionTrack`'s curve.

    Each segment endpoint (``p1``) is a draggable circle; cubic-bezier
    segments also expose their ``c0`` and ``c1`` as smaller handles.
    Mouse drag updates the underlying segment in place and emits
    :attr:`track_modified` so the workspace can refresh the player
    or persist the change.

    Value-axis range is taken from the bound parameter when the
    workspace passes one in; otherwise we use a symmetric ``[-1, 1]``
    range which matches every Cubism-style parameter we ship."""

    track_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(QColor(35, 35, 40)))
        self._motion: Motion | None = None
        self._track: MotionTrack | None = None
        self._duration: float = 1.0
        self._value_min: float = -1.0
        self._value_max: float = 1.0

    def set_track(
        self,
        motion: Motion | None,
        track: MotionTrack | None,
        *,
        value_min: float = -1.0,
        value_max: float = 1.0,
    ) -> None:
        self._motion = motion
        self._track = track
        self._duration = float(motion.duration) if motion is not None else 1.0
        self._value_min = float(value_min)
        self._value_max = float(value_max)
        self._rebuild()

    def motion(self) -> Motion | None:
        return self._motion

    def track(self) -> MotionTrack | None:
        return self._track

    # ---- rebuild --------------------------------------------------------

    def _rebuild(self) -> None:
        self._scene.clear()
        self._scene.setSceneRect(0.0, 0.0, _SCENE_WIDTH, _SCENE_HEIGHT)
        self._draw_grid()
        if self._track is None:
            return
        self._draw_segments()

    def _draw_grid(self) -> None:
        pen = QPen(QColor(60, 60, 70))
        # Horizontal grid line at value = 0.
        zero_y = self._value_to_y(0.0)
        self._scene.addLine(_MARGIN, zero_y, _SCENE_WIDTH - _MARGIN, zero_y, pen)
        # Border frame.
        frame = QPen(QColor(80, 80, 95))
        self._scene.addRect(
            QRectF(
                _MARGIN, _MARGIN,
                _SCENE_WIDTH - 2 * _MARGIN, _SCENE_HEIGHT - 2 * _MARGIN,
            ),
            frame,
        )

    def _draw_segments(self) -> None:
        assert self._track is not None
        curve_pen = QPen(QColor(150, 200, 255), 2)
        ctrl_pen = QPen(QColor(160, 120, 200), 1, Qt.PenStyle.DashLine)
        for index, segment in enumerate(self._track.segments):
            p0 = self._scene_point(*segment.p0)
            p1 = self._scene_point(*segment.p1)
            self._scene.addLine(QGraphicsLineItem(p0.x(), p0.y(), p1.x(), p1.y()).line(), curve_pen)
            if segment.type == "cubic-bezier" and segment.c0 and segment.c1:
                c0 = self._scene_point(*segment.c0)
                c1 = self._scene_point(*segment.c1)
                # Dashed lines from endpoints to control handles.
                self._scene.addLine(p0.x(), p0.y(), c0.x(), c0.y(), ctrl_pen)
                self._scene.addLine(p1.x(), p1.y(), c1.x(), c1.y(), ctrl_pen)
                self._scene.addItem(_ControlHandle(
                    self, segment_index=index, field="c0",
                    center=c0, color=QColor(220, 150, 220),
                ))
                self._scene.addItem(_ControlHandle(
                    self, segment_index=index, field="c1",
                    center=c1, color=QColor(220, 150, 220),
                ))
            # p1 endpoint handle. The first segment's p0 is the curve's
            # absolute start; subsequent segments share p0 with the
            # previous p1, so we only render p1 to avoid stacking.
            self._scene.addItem(_EndpointHandle(
                self, segment_index=index, center=p1,
            ))
        # Render the very first p0 too so the user can drag the start.
        if self._track.segments:
            start = self._scene_point(*self._track.segments[0].p0)
            self._scene.addItem(_EndpointHandle(
                self, segment_index=0, center=start, is_start=True,
            ))

    # ---- coordinate mapping --------------------------------------------

    def _scene_point(self, t: float, v: float) -> QPointF:
        return QPointF(self._time_to_x(t), self._value_to_y(v))

    def scene_to_track(self, point: QPointF) -> tuple[float, float]:
        return self._x_to_time(point.x()), self._y_to_value(point.y())

    def _time_to_x(self, t: float) -> float:
        usable = _SCENE_WIDTH - 2 * _MARGIN
        if self._duration <= 0:
            return _MARGIN
        return _MARGIN + (t / self._duration) * usable

    def _x_to_time(self, x: float) -> float:
        usable = _SCENE_WIDTH - 2 * _MARGIN
        if usable <= 0:
            return 0.0
        return max(0.0, min(self._duration, (x - _MARGIN) / usable * self._duration))

    def _value_to_y(self, v: float) -> float:
        usable = _SCENE_HEIGHT - 2 * _MARGIN
        span = self._value_max - self._value_min
        if span <= 0:
            return _SCENE_HEIGHT / 2.0
        # Y axis is inverted so higher values render upward.
        norm = (v - self._value_min) / span
        return _SCENE_HEIGHT - _MARGIN - norm * usable

    def _y_to_value(self, y: float) -> float:
        usable = _SCENE_HEIGHT - 2 * _MARGIN
        if usable <= 0:
            return self._value_min
        norm = (_SCENE_HEIGHT - _MARGIN - y) / usable
        return self._value_min + norm * (self._value_max - self._value_min)

    # ---- mutation -------------------------------------------------------

    def update_endpoint(
        self, segment_index: int, point: QPointF, *, is_start: bool = False,
    ) -> None:
        if self._track is None:
            return
        if not 0 <= segment_index < len(self._track.segments):
            return
        t, v = self.scene_to_track(point)
        segment = self._track.segments[segment_index]
        if is_start:
            segment.p0 = (t, v)
        else:
            segment.p1 = (t, v)
            # Keep the following segment's p0 in sync — Cubism's contract
            # is that segment[i].p1 == segment[i+1].p0.
            if segment_index + 1 < len(self._track.segments):
                self._track.segments[segment_index + 1].p0 = (t, v)
        self._rebuild()
        self.track_modified.emit()

    def update_control(
        self, segment_index: int, field: str, point: QPointF,
    ) -> None:
        if self._track is None or field not in ("c0", "c1"):
            return
        if not 0 <= segment_index < len(self._track.segments):
            return
        t, v = self.scene_to_track(point)
        segment = self._track.segments[segment_index]
        if field == "c0":
            segment.c0 = (t, v)
        else:
            segment.c1 = (t, v)
        self._rebuild()
        self.track_modified.emit()


# ---------------------------------------------------------------------------
# Handle items
# ---------------------------------------------------------------------------


class _EndpointHandle(QGraphicsEllipseItem):
    def __init__(
        self,
        view: MotionTimelineWidget,
        *,
        segment_index: int,
        center: QPointF,
        is_start: bool = False,
    ):
        super().__init__(
            -_ENDPOINT_RADIUS, -_ENDPOINT_RADIUS,
            _ENDPOINT_RADIUS * 2, _ENDPOINT_RADIUS * 2,
        )
        self.setBrush(QBrush(QColor(240, 220, 120)))
        self.setPen(QPen(QColor(60, 60, 60)))
        self.setPos(center)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setZValue(2.0)
        self._view = view
        self._segment_index = segment_index
        self._is_start = is_start

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._view.update_endpoint(
                self._segment_index, value, is_start=self._is_start,
            )
        return super().itemChange(change, value)


class _ControlHandle(QGraphicsEllipseItem):
    def __init__(
        self,
        view: MotionTimelineWidget,
        *,
        segment_index: int,
        field: str,
        center: QPointF,
        color: QColor,
    ):
        super().__init__(
            -_CONTROL_RADIUS, -_CONTROL_RADIUS,
            _CONTROL_RADIUS * 2, _CONTROL_RADIUS * 2,
        )
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor(60, 60, 60)))
        self.setPos(center)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setZValue(2.5)
        self._view = view
        self._segment_index = segment_index
        self._field = field

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._view.update_control(self._segment_index, self._field, value)
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# Dialog wrapper
# ---------------------------------------------------------------------------


class MotionTimelineDialog(QDialog):
    """Modal-ish dialog wrapping a :class:`MotionTimelineWidget` with a
    track picker. The workspace hands it the active motion; the user
    picks one of the motion's tracks and edits the curve in place."""

    def __init__(self, motion: Motion, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(parent)
        self.setWindowTitle(
            lang.get("puppet_timeline_title", "Edit motion timeline"),
        )
        self.setMinimumSize(880, 380)
        layout = QVBoxLayout(self)

        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel(
            lang.get("puppet_timeline_track", "Track:"),
        ))
        self._track_picker = QComboBox()
        for track in motion.tracks:
            self._track_picker.addItem(track.param_id)
        self._track_picker.currentIndexChanged.connect(self._on_track_changed)
        picker_row.addWidget(self._track_picker, stretch=1)
        layout.addLayout(picker_row)

        self._view = MotionTimelineWidget()
        layout.addWidget(self._view, stretch=1)

        self._motion = motion
        if motion.tracks:
            self._on_track_changed(0)

    def widget(self) -> MotionTimelineWidget:
        return self._view

    def _on_track_changed(self, index: int) -> None:
        if not 0 <= index < len(self._motion.tracks):
            self._view.set_track(None, None)
            return
        self._view.set_track(self._motion, self._motion.tracks[index])
