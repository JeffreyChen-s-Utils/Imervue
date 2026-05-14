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
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

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
        self._frame_label.setStyleSheet("background: #111;")

        self._status_label = QLabel(self)
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)

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

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(int(1000 / _POLL_HZ))
        self._poll_timer.timeout.connect(self._refresh)
        self._refresh()   # seed with a status line before the first poll

    # ---- lifecycle -----------------------------------------------------

    def showEvent(self, event):   # pragma: no cover - Qt event plumbing
        super().showEvent(event)
        self._poll_timer.start()

    def hideEvent(self, event):   # pragma: no cover - Qt event plumbing
        self._poll_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):   # pragma: no cover - Qt event plumbing
        # Closing the dialog should also stop tracking — otherwise the
        # camera light stays on with no UI to surface it. The workspace
        # is wired to listen for this so it can also untick the
        # Webcam-tracking toolbar toggle.
        self._tracker.set_enabled(False)
        super().closeEvent(event)

    # ---- private -------------------------------------------------------

    def _on_stop_clicked(self) -> None:
        self._tracker.set_enabled(False)
        self.close()

    def _refresh(self) -> None:
        state = self._tracker.current_preview_state()
        self._update_frame(state)
        self._update_status(state)

    def _update_frame(self, state: dict) -> None:
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
    # QImage.mirrored() takes positional args in PySide6; horizontal
    # flip only, no vertical.
    image = QImage(
        frame_bgr.tobytes(),
        w, h,
        w * 3,
        QImage.Format.Format_BGR888,
    ).mirrored(True, False)
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
