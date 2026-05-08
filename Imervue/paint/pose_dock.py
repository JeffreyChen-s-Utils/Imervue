"""Pose reference dock — interactive 2D stick-figure poser.

A simplified stand-in for a 3D model viewer: the user drags joints
of a fixed-skeleton stick figure inside the dock's canvas, then
clicks **Insert** to stamp the current pose into the active paint
canvas as a guides layer.

Embeds a custom :class:`PoseCanvas` widget that paints the skeleton
with QPainter and translates mouse events into joint moves on the
underlying :class:`PoseSkeleton`. Joints are clamped into the unit
square so a stray drag can never push a limb permanently off-screen.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.pose_skeleton import (
    PoseSkeleton,
    default_skeleton,
)

CANVAS_PX = 240
DRAG_HIT_RADIUS = 14


class PoseDock(QDockWidget):
    """Dockable pose-reference panel.

    Emits ``insert_requested`` with the current :class:`PoseSkeleton`
    when the user clicks *Insert*. The workspace renders the
    skeleton into a new layer on the active canvas.
    """

    insert_requested = Signal(object)

    def __init__(self, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_pose", "Pose"), parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        self._canvas = PoseCanvas()
        layout.addWidget(self._canvas)

        button_row = QHBoxLayout()
        reset_btn = QPushButton(
            lang.get("paint_pose_reset", "Reset pose"),
        )
        reset_btn.clicked.connect(self._on_reset)
        reset_btn.setToolTip(lang.get(
            "paint_pose_reset_tooltip",
            "Restore the skeleton to its default neutral pose",
        ))
        insert_btn = QPushButton(
            lang.get("paint_pose_insert", "Insert into canvas"),
        )
        insert_btn.clicked.connect(self._on_insert)
        insert_btn.setToolTip(lang.get(
            "paint_pose_insert_tooltip",
            "Render the skeleton into a new layer at canvas size",
        ))
        button_row.addWidget(reset_btn)
        button_row.addWidget(insert_btn)
        layout.addLayout(button_row)

        self.setWidget(body)

    def skeleton(self) -> PoseSkeleton:
        return self._canvas.skeleton()

    def _on_reset(self) -> None:
        self._canvas.reset_skeleton()

    def _on_insert(self) -> None:
        self.insert_requested.emit(self._canvas.skeleton())


class PoseCanvas(QWidget):
    """Custom QWidget that paints + edits the skeleton."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Min-size keeps the figure usable when the dock is small,
        # but the size policy lets it grow to fill whatever the dock
        # gives us — undocking the pose panel into a 600×800 floater
        # gives a 600×800 posing canvas instead of a stranded
        # 240×240 square in the corner.
        self.setMinimumSize(CANVAS_PX, CANVAS_PX)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setMouseTracking(True)
        self._skeleton = default_skeleton()
        self._dragging: str | None = None

    def skeleton(self) -> PoseSkeleton:
        return self._skeleton

    def reset_skeleton(self) -> None:
        self._skeleton = default_skeleton()
        self.update()

    # ---- painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: ARG002, N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect()
            # Background — a light card so the dark skeleton reads.
            painter.fillRect(rect, QColor("#202022"))
            # Bones first, joints on top.
            bone_pen = QPen(QColor(220, 220, 220, 240))
            bone_pen.setWidth(3)
            painter.setPen(bone_pen)
            for bone in self._skeleton.bones:
                a = self._skeleton.joints.get(bone.a)
                b = self._skeleton.joints.get(bone.b)
                if a is None or b is None:
                    continue
                painter.drawLine(
                    int(a.x * rect.width()), int(a.y * rect.height()),
                    int(b.x * rect.width()), int(b.y * rect.height()),
                )
            painter.setPen(QPen(QColor(255, 90, 90, 240), 2))
            for joint in self._skeleton.joints.values():
                cx = int(joint.x * rect.width())
                cy = int(joint.y * rect.height())
                r = max(3, joint.radius_px // 2)
                painter.drawEllipse(QPoint(cx, cy), r, r)
        finally:
            painter.end()

    # ---- mouse ------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        target = self._joint_at(event.position().x(), event.position().y())
        if target is not None:
            self._dragging = target

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging is None:
            return
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        x = event.position().x() / rect.width()
        y = event.position().y() / rect.height()
        self._skeleton.move_joint(self._dragging, x, y)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = None

    def _joint_at(self, px: float, py: float) -> str | None:
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        radius_sq = DRAG_HIT_RADIUS ** 2
        nearest_name = None
        nearest_dist_sq = radius_sq
        for joint in self._skeleton.joints.values():
            jx = joint.x * rect.width()
            jy = joint.y * rect.height()
            dist_sq = (jx - px) ** 2 + (jy - py) ** 2
            if dist_sq <= nearest_dist_sq:
                nearest_dist_sq = dist_sq
                nearest_name = joint.name
        return nearest_name


