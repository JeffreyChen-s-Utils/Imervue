"""Live preview window for the webcam tracking flow.

Without this dialog the user clicks **Webcam tracking** and gets…
nothing — the rig may or may not start moving, the camera light may
or may not come on, and if the deps are missing or the camera is
busy the only feedback is a status-bar message that often gets
overlooked. This pops a small floating window that mirrors the
camera frame, overlays detected face-mesh landmarks, and prints a
status line so the user can immediately tell whether the pipeline
is alive.

Pure Qt — uses QLabel + QPixmap rather than a QOpenGLWidget so it
works on machines where the puppet canvas's GL context isn't
available (e.g. running on a remote desktop). 30 Hz polling of
:meth:`WebcamTracker.current_preview_state` keeps the UI work off
the capture thread.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.webcam_status import WebcamPhase, status_text

if TYPE_CHECKING:
    from Imervue.puppet.webcam_tracker import WebcamTracker


_POLL_HZ: int = 30
_PREVIEW_MIN_SIZE: tuple[int, int] = (480, 360)
# A handful of mesh landmark indices we paint as overlay markers —
# eyes, eyebrows, nose tip, mouth corners. These are enough for the
# user to verify "the tracker is locked onto my face" without
# drawing the full 468-point wireframe (which slows the preview).
_LANDMARK_OVERLAY_INDICES: tuple[int, ...] = (
    1,            # nose tip
    33, 133,      # left eye outer / inner
    362, 263,     # right eye inner / outer
    61, 291,      # mouth left / right corners
    13, 14,       # upper / lower lip centre
    105, 334,     # eyebrow inner points
)


class WebcamPreviewDialog(QDialog):
    """Floating preview window bound to a :class:`WebcamTracker`."""

    install_requested = Signal()

    def __init__(self, tracker: WebcamTracker, parent=None):
        super().__init__(parent)
        self._tracker = tracker
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("puppet_webcam_preview_title", "Webcam tracking"))
        # Tool-style window: stays above the workspace but doesn't
        # steal focus, and has no taskbar entry.
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumSize(*_PREVIEW_MIN_SIZE)

        self._frame_label = QLabel(self)
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._frame_label.setMinimumSize(*_PREVIEW_MIN_SIZE)
        self._frame_label.setStyleSheet("background: #111; color: #eee; padding: 8px;")

        self._status_label = QLabel(self)
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._status_label.setWordWrap(True)

        self._stop_button = QPushButton(
            lang.get("puppet_webcam_preview_stop", "Stop tracking"), self,
        )
        self._stop_button.clicked.connect(self._on_stop_clicked)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._status_label, stretch=1)
        bottom_row.addWidget(self._stop_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._frame_label, stretch=1)
        layout.addLayout(bottom_row)
        self._build_recovery_controls(layout)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(int(1000 / _POLL_HZ))
        self._poll_timer.timeout.connect(self._refresh)
        self._refresh()   # seed with a status line before the first poll

    def _build_recovery_controls(self, layout: QVBoxLayout) -> None:
        lang = language_wrapper.language_word_dict
        row = QHBoxLayout()
        device_label = QLabel(lang.get("webcam_device", "Camera index"))
        self._device = QSpinBox()
        self._device.setRange(0, 64)
        self._device.setValue(self._tracker.status().device)
        self._device.setToolTip(lang.get(
            "webcam_device_hint",
            "0 is the default camera. Try another index if it is unavailable.",
        ))
        device_label.setBuddy(self._device)
        self._retry_button = QPushButton(lang.get("webcam_retry", "Start / retry"))
        self._retry_button.clicked.connect(self._retry)
        self._install_button = QPushButton(lang.get("webcam_install", "Install tracking packages"))
        self._install_button.clicked.connect(self.install_requested)
        for widget in (device_label, self._device, self._retry_button, self._install_button):
            row.addWidget(widget)
        layout.addLayout(row)
        self._diagnostics = QLabel()
        self._diagnostics.setTextFormat(Qt.TextFormat.PlainText)
        self._diagnostics.setWordWrap(True)
        self._diagnostics.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._diagnostics)

    def _retry(self) -> None:
        if self._tracker.set_device(self._device.value()):
            self._tracker.set_enabled(True)
        self._refresh()

    # ---- lifecycle -----------------------------------------------------

    def showEvent(self, event):   # pragma: no cover - Qt event plumbing
        super().showEvent(event)
        self._poll_timer.start()

    def hideEvent(self, event):   # pragma: no cover - Qt event plumbing
        self._poll_timer.stop()
        super().hideEvent(event)

    def done(self, result: int) -> None:
        """Stop on Escape, the Stop button and a close while visible."""
        self._tracker.set_enabled(False)
        super().done(result)

    def closeEvent(self, event) -> None:
        """Stop on a close QDialog does not route through done(): a hidden or unshown dialog."""
        self._tracker.set_enabled(False)
        super().closeEvent(event)

    # ---- private -------------------------------------------------------

    def _on_stop_clicked(self) -> None:
        self.reject()

    def _refresh(self) -> None:
        state = self._tracker.current_preview_state()
        self._update_frame(state)
        status = self._tracker.status()
        if status.phase == WebcamPhase.RUNNING:
            self._update_status(state)
        else:
            self._status_label.setText(status_text(status, language_wrapper.language_word_dict))
        configurable = self._tracker.can_configure()
        self._device.setEnabled(configurable)
        self._retry_button.setEnabled(configurable)
        self._install_button.setVisible(status.phase == WebcamPhase.MISSING_DEPENDENCY)
        self._stop_button.setEnabled(status.active)
        self._diagnostics.setText(status.detail)
        self._diagnostics.setVisible(bool(status.detail))

    def _update_frame(self, state: dict) -> None:
        status = self._tracker.status()
        if not status.active:
            self._frame_label.setText(status_text(status, language_wrapper.language_word_dict))
            self._frame_label.setWordWrap(True)
            return
        frame = state.get("frame_bgr")
        if frame is None:
            self._frame_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_webcam_preview_waiting",
                    "Waiting for first frame…",
                ),
            )
            return
        landmarks = state.get("landmarks_norm")
        pixmap = _frame_to_pixmap(frame, landmarks)
        # Scale to fit the label while preserving aspect ratio.
        label_size = self._frame_label.size()
        scaled = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._frame_label.setPixmap(scaled)

    def _update_status(self, state: dict) -> None:
        lang = language_wrapper.language_word_dict
        if state.get("error"):
            self._status_label.setText(
                lang.get(
                    "puppet_webcam_preview_error",
                    "Error: {message}",
                ).format(message=state["error"]),
            )
            return
        if not state.get("camera_open"):
            self._status_label.setText(
                lang.get(
                    "puppet_webcam_preview_opening",
                    "Opening camera…",
                ),
            )
            return
        face_msg = (
            lang.get(
                "puppet_webcam_preview_face_locked", "Face detected",
            )
            if state.get("face_detected")
            else lang.get(
                "puppet_webcam_preview_no_face", "No face in frame",
            )
        )
        self._status_label.setText(
            lang.get(
                "puppet_webcam_preview_status",
                "{face} · {fps:.1f} fps",
            ).format(face=face_msg, fps=state.get("fps", 0.0)),
        )


def _frame_to_pixmap(
    frame_bgr: np.ndarray, landmarks_norm: np.ndarray | None,
) -> QPixmap:
    """Convert a cv2 BGR frame into a QPixmap with landmark overlay.

    Pure helper so unit tests can exercise the conversion + overlay
    pipeline without instantiating the dialog (which needs Qt's
    event loop). Landmarks come in mediapipe's normalised [0, 1]
    coordinates; we paint them as 4-pixel circles on top of the
    image.
    """
    if frame_bgr.ndim != 3 or frame_bgr.shape[-1] != 3:
        raise ValueError("expected H×W×3 BGR frame")
    h, w = frame_bgr.shape[:2]
    # cv2's native byte order is BGR; QImage's Format_BGR888 reads
    # those bytes directly without an intermediate copy.
    # Webcam frames are usually mirrored ("selfie view"); flip
    # horizontally so the user sees themselves the right way round.
    # ``flipped`` rather than the two-bool ``mirrored`` overload: Qt
    # deprecated the latter, and it warns on every frame at 30 fps.
    image = QImage(
        frame_bgr.tobytes(),
        w, h,
        w * 3,
        QImage.Format.Format_BGR888,
    ).flipped(Qt.Orientation.Horizontal)
    pixmap = QPixmap.fromImage(image)
    if landmarks_norm is None or len(landmarks_norm) == 0:
        return pixmap
    painter = QPainter(pixmap)
    try:
        pen = QPen(Qt.GlobalColor.green)
        pen.setWidth(3)
        painter.setPen(pen)
        n = len(landmarks_norm)
        for idx in _LANDMARK_OVERLAY_INDICES:
            if idx >= n:
                continue
            x_norm, y_norm = float(landmarks_norm[idx][0]), float(landmarks_norm[idx][1])
            # Mirror x to match the mirrored frame.
            x = int((1.0 - x_norm) * w)
            y = int(y_norm * h)
            painter.drawEllipse(x - 3, y - 3, 6, 6)
    finally:
        painter.end()
    return pixmap
