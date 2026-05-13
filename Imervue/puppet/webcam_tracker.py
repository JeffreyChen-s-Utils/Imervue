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
        # Preview snapshot — shared with the preview dialog so the user
        # can see what the camera is producing without staring at a
        # frozen-looking puppet. Frame is BGR (cv2's native format),
        # landmarks are in mediapipe's normalised [0, 1] coords so the
        # dialog can paint them at whatever zoom it ends up using.
        self._latest_frame_bgr: np.ndarray | None = None
        self._latest_landmarks_norm: np.ndarray | None = None
        self._face_detected: bool = False
        self._fps: float = 0.0
        self._camera_open: bool = False
        self._error_message: str | None = None
        self._preview_lock = threading.Lock()
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

    def current_preview_state(self) -> dict:
        """Snapshot of the most recent capture for the preview dialog.

        Returns a fresh ``dict`` (no shared references) safe to use on
        the GUI thread:

        ``frame_bgr`` — latest cv2 frame (H×W×3 uint8) or ``None``
        ``landmarks_norm`` — N×3 array in mediapipe's normalised
        coords, or ``None`` when no face is detected
        ``face_detected`` — bool, mirrors the last frame's outcome
        ``fps`` — measured capture FPS (EMA over recent frames)
        ``camera_open`` — True once VideoCapture(0) opened cleanly
        ``error`` — optional one-line error string from the worker
        """
        with self._preview_lock:
            return {
                "frame_bgr": (
                    None if self._latest_frame_bgr is None
                    else self._latest_frame_bgr.copy()
                ),
                "landmarks_norm": (
                    None if self._latest_landmarks_norm is None
                    else self._latest_landmarks_norm.copy()
                ),
                "face_detected": self._face_detected,
                "fps": self._fps,
                "camera_open": self._camera_open,
                "error": self._error_message,
            }

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
        try:
            landmarker = _build_face_landmarker(mp)
        except _WebcamSetupError as exc:
            with self._preview_lock:
                self._camera_open = False
                self._error_message = str(exc)
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("webcam open failed")
            with self._preview_lock:
                self._camera_open = False
                self._error_message = "VideoCapture(0) returned no device"
            landmarker.close()
            return
        with self._preview_lock:
            self._camera_open = True
            self._error_message = None
        # EMA-smoothed FPS so the preview status doesn't jitter every
        # frame; alpha 0.1 gives a ~10-frame window.
        fps_ema = 0.0
        try:
            while not self._stop_evt.is_set():
                start = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(_FRAME_INTERVAL_S)
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                landmarks_norm = _detect_face(landmarker, mp, rgb)
                if landmarks_norm is not None:
                    params = landmarks_to_params(landmarks_norm)
                    with self._params_lock:
                        self._latest_params = params
                elapsed = time.monotonic() - start
                inst_fps = 1.0 / elapsed if elapsed > 0 else 0.0
                fps_ema = inst_fps if fps_ema == 0.0 else (0.9 * fps_ema + 0.1 * inst_fps)
                # Mirror the latest capture under the preview lock so
                # the dialog (running on the GUI thread) can paint it.
                with self._preview_lock:
                    self._latest_frame_bgr = frame
                    self._latest_landmarks_norm = landmarks_norm
                    self._face_detected = landmarks_norm is not None
                    self._fps = float(fps_ema)
                remaining = _FRAME_INTERVAL_S - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            cap.release()
            landmarker.close()
            with self._preview_lock:
                self._camera_open = False

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
    """Convert mediapipe ``Tasks API`` landmark output into an
    ``(N, 3)`` float64 numpy array. The Tasks API returns a list of
    ``NormalizedLandmark`` with ``.x / .y / .z`` attributes, so the
    shape is the same as the old ``solutions`` API."""
    return np.asarray(
        [(lm.x, lm.y, lm.z) for lm in face_landmarks],
        dtype=np.float64,
    )


# ---------------------------------------------------------------------------
# mediapipe Tasks API plumbing
# ---------------------------------------------------------------------------
#
# Modern mediapipe (≥ 0.11) removed the legacy ``solutions.face_mesh``
# module entirely. Detection now goes through
# ``mediapipe.tasks.vision.FaceLandmarker``, which takes an asset
# bundle (the ``.task`` file) rather than carrying the model weights
# inside the wheel. We auto-download the official Google-hosted
# model on first use and cache it under ``<app_dir>/models/``.

_FACE_LANDMARKER_MODEL_URL: str = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


class _WebcamSetupError(RuntimeError):
    """Raised by ``_build_face_landmarker`` when the Tasks API can't
    be initialised (missing model file, download failure, or import
    error after a partial install). The capture loop converts it
    into a user-visible ``_error_message`` on the preview snapshot."""


def _https_urlopen(url: str):   # noqa: ANN201 - urllib return type
    """HTTPS-only urlopen guard.

    Mirrors the canonical guards in ``Imervue/plugin/pip_installer.py``
    and ``Imervue/plugin/plugin_downloader.py`` so this module's
    network call also passes the SonarQube ``python:S5332`` / bandit
    ``B310`` audit. Any non-HTTPS scheme is rejected before the call
    is made; never call ``urllib.request.urlopen`` directly from this
    module."""
    from urllib import request
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise _WebcamSetupError(
            f"refusing non-HTTPS URL for landmark model: {url}",
        )
    return request.urlopen(url, timeout=30)   # nosec B310  # scheme validated above


def _face_landmarker_model_path():
    """Return the on-disk path to ``face_landmarker.task``. Downloads
    on first use; returns the path even on download failure so the
    caller can raise a clean ``_WebcamSetupError`` with the failure
    reason rather than a deep ``urllib`` traceback."""
    from Imervue.system.app_paths import app_dir

    target = app_dir() / "models" / "face_landmarker.task"
    if target.is_file() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.info("downloading face_landmarker.task to %s", target)
    try:
        with _https_urlopen(_FACE_LANDMARKER_MODEL_URL) as resp:
            data = resp.read()
        target.write_bytes(data)
    except OSError as exc:
        raise _WebcamSetupError(
            f"failed to download face_landmarker.task: {exc}",
        ) from exc
    return target


def _build_face_landmarker(mp):
    """Wire up a mediapipe Tasks-API ``FaceLandmarker``.

    Returns the live detector; raises :class:`_WebcamSetupError` with
    a user-readable reason if either the Tasks API is unavailable
    (very old mediapipe) or the model can't be located. The capture
    thread catches that exception and surfaces it through the
    preview snapshot."""
    try:
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError as exc:
        raise _WebcamSetupError(
            "mediapipe.tasks not available — please install "
            "mediapipe >= 0.10",
        ) from exc
    model_path = _face_landmarker_model_path()
    options = mp_vision.FaceLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    return mp_vision.FaceLandmarker.create_from_options(options)


def _detect_face(landmarker, mp, rgb_frame) -> np.ndarray | None:
    """Run one detection pass and return the landmark array (or
    ``None`` when no face is visible).

    Wraps the Tasks API quirks: VIDEO running mode wants a monotonic
    timestamp in milliseconds, and the result's ``face_landmarks`` is
    a list of per-face landmark lists. We always ask for one face so
    the first entry is the only entry."""
    timestamp_ms = int(time.monotonic() * 1000.0)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    try:
        result = landmarker.detect_for_video(mp_image, timestamp_ms)
    except RuntimeError as exc:
        # The detector occasionally raises when the timestamp goes
        # non-monotonic (e.g. webcam reconnect). One missed frame is
        # harmless; logging at debug keeps the loop quiet.
        logger.debug("face landmarker frame skipped: %s", exc)
        return None
    if not result.face_landmarks:
        return None
    return _landmarks_to_array(result.face_landmarks[0])
