"""Webcam → puppet parameter pump.

A :class:`WebcamTracker` runs OpenCV's ``VideoCapture`` + mediapipe's
FaceMesh on a background thread, computes parameter values via
:mod:`face_landmark_mapper`, and pushes them into the bound
:class:`PuppetCanvas` via a queued slot. Optional deps (``cv2``,
``mediapipe``) are imported behind ``try / except`` so the rest of
the plugin works even when they're missing — ``set_enabled(True)``
returns ``False`` in that case so the workspace can show a hint.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.face_landmark_mapper import landmarks_to_params

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas

logger = logging.getLogger("Imervue.plugin.puppet.webcam_tracker")

_TARGET_FPS: int = 30
_FRAME_INTERVAL_S: float = 1.0 / _TARGET_FPS


class WebcamTracker(QObject):
    """Toggle-on optical face tracking for the Puppet canvas."""

    state_changed = Signal()

    def __init__(self, canvas: PuppetCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._enabled = False
        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._latest_params: dict[str, float] = {}
        self._params_lock = threading.Lock()
        self._pump_timer = QTimer(self)
        self._pump_timer.setInterval(int(1000 / _TARGET_FPS))
        self._pump_timer.timeout.connect(self._pump_to_canvas)

    # ---- public --------------------------------------------------------

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> bool:
        """Toggle tracking. Returns ``True`` if the requested state
        was reached. Returns ``False`` and stays off if the optional
        deps (cv2 / mediapipe) are missing or the camera open failed."""
        if enabled == self._enabled:
            return True
        if enabled:
            ok = self._start()
            if not ok:
                self._enabled = False
                self.state_changed.emit()
                return False
        else:
            self._stop()
        self._enabled = bool(enabled)
        self.state_changed.emit()
        return True

    def shutdown(self) -> None:
        self._stop()

    # ---- start / stop --------------------------------------------------

    def _start(self) -> bool:
        try:
            import cv2   # noqa: F401 - probe import
            import mediapipe   # noqa: F401 - probe import
        except ImportError:
            logger.info("cv2 / mediapipe not installed; webcam tracking unavailable")
            return False
        self._stop_evt.clear()
        try:
            self._thread = threading.Thread(
                target=self._tracking_loop, daemon=True,
            )
            self._thread.start()
        except RuntimeError as exc:
            logger.warning("webcam thread failed: %s", exc)
            return False
        self._pump_timer.start()
        return True

    def _stop(self) -> None:
        self._stop_evt.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._pump_timer.stop()

    # ---- background loop -----------------------------------------------

    def _tracking_loop(self) -> None:  # pragma: no cover - needs camera + mediapipe
        import cv2
        import mediapipe as mp
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("webcam open failed")
            return
        mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5,
        )
        try:
            while not self._stop_evt.is_set():
                start = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(_FRAME_INTERVAL_S)
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = mesh.process(rgb)
                if result.multi_face_landmarks:
                    landmarks = _landmarks_to_array(result.multi_face_landmarks[0])
                    params = landmarks_to_params(landmarks)
                    with self._params_lock:
                        self._latest_params = params
                elapsed = time.monotonic() - start
                remaining = _FRAME_INTERVAL_S - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            cap.release()
            mesh.close()

    # ---- GUI thread pump -----------------------------------------------

    def _pump_to_canvas(self) -> None:
        if not self._enabled or self._canvas.document() is None:
            return
        with self._params_lock:
            params = dict(self._latest_params)
        if not params:
            return
        for param_id, value in params.items():
            self._canvas.set_parameter_value(param_id, value)


def _landmarks_to_array(face_landmarks) -> np.ndarray:  # pragma: no cover - mediapipe types
    return np.asarray(
        [(lm.x, lm.y, lm.z) for lm in face_landmarks.landmark],
        dtype=np.float64,
    )
