"""Pure-Python mapper from MediaPipe FaceMesh landmarks → puppet
parameters.

The 478-landmark FaceMesh schema has stable indices for left / right
eye corners, mouth corners, nose tip, etc. This module turns those
landmarks into ``ParamAngleX / Y / Z``, eye openness, mouth openness
values in roughly ``[-1, 1]`` so the existing parameter-sampling
pipeline can consume them.

Lives in its own module (no Qt, no mediapipe import) so the math is
testable and the optional-dep boundary is clean — the live tracker
in ``webcam_tracker.py`` calls into here.
"""
from __future__ import annotations

import math

import numpy as np

# MediaPipe FaceMesh landmark indices (478-point model).
LANDMARK_NOSE_TIP: int = 4
LANDMARK_LEFT_EYE_OUTER: int = 263
LANDMARK_LEFT_EYE_INNER: int = 362
LANDMARK_LEFT_EYE_TOP: int = 386
LANDMARK_LEFT_EYE_BOTTOM: int = 374
LANDMARK_RIGHT_EYE_OUTER: int = 33
LANDMARK_RIGHT_EYE_INNER: int = 133
LANDMARK_RIGHT_EYE_TOP: int = 159
LANDMARK_RIGHT_EYE_BOTTOM: int = 145
LANDMARK_MOUTH_LEFT: int = 61
LANDMARK_MOUTH_RIGHT: int = 291
LANDMARK_MOUTH_TOP: int = 13
LANDMARK_MOUTH_BOTTOM: int = 14
LANDMARK_LEFT_TEMPLE: int = 234
LANDMARK_RIGHT_TEMPLE: int = 454

# Open / closed reference distances (normalised against face width).
_EYE_OPEN_THRESHOLD: float = 0.04
_EYE_CLOSED_THRESHOLD: float = 0.012
_MOUTH_OPEN_CEILING: float = 0.10


def landmarks_to_params(landmarks: np.ndarray) -> dict[str, float]:
    """Translate a (478, 3) landmark array into puppet parameter
    values. Returns an empty dict if the input is malformed.

    Coordinate system: mediapipe normalises landmarks to ``[0, 1]``
    relative to the input frame, and ``z`` is roughly camera-relative
    depth (more negative = closer). We collapse this into the same
    ``[-1, 1]`` parameter range used by Cubism-shaped rigs.
    """
    if landmarks.ndim != 2 or landmarks.shape[1] < 2 or landmarks.shape[0] < 468:
        return {}
    return {
        "ParamAngleX": _head_yaw(landmarks),
        "ParamAngleY": _head_pitch(landmarks),
        "ParamAngleZ": _head_roll(landmarks),
        "ParamEyeLOpen": _eye_open(
            landmarks, LANDMARK_LEFT_EYE_TOP, LANDMARK_LEFT_EYE_BOTTOM,
        ),
        "ParamEyeROpen": _eye_open(
            landmarks, LANDMARK_RIGHT_EYE_TOP, LANDMARK_RIGHT_EYE_BOTTOM,
        ),
        "ParamMouthOpenY": _mouth_open(landmarks),
    }


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def _face_width(landmarks: np.ndarray) -> float:
    left = landmarks[LANDMARK_LEFT_TEMPLE]
    right = landmarks[LANDMARK_RIGHT_TEMPLE]
    return float(np.linalg.norm(left[:2] - right[:2])) or 1e-6


def _head_yaw(landmarks: np.ndarray) -> float:
    """Approximate head yaw from nose-tip horizontal offset relative to
    the temple midpoint. Positive = facing right (camera POV)."""
    nose = landmarks[LANDMARK_NOSE_TIP]
    left = landmarks[LANDMARK_LEFT_TEMPLE]
    right = landmarks[LANDMARK_RIGHT_TEMPLE]
    mid_x = (left[0] + right[0]) / 2.0
    width = max(abs(right[0] - left[0]), 1e-6)
    yaw = (nose[0] - mid_x) / (width / 2.0)
    return float(np.clip(yaw * 1.3, -1.0, 1.0))


def _head_pitch(landmarks: np.ndarray) -> float:
    """Approximate pitch from nose Y vs eye-line Y. Positive = looking
    up (camera POV)."""
    nose = landmarks[LANDMARK_NOSE_TIP]
    left_eye = landmarks[LANDMARK_LEFT_EYE_OUTER]
    right_eye = landmarks[LANDMARK_RIGHT_EYE_OUTER]
    eye_line_y = (left_eye[1] + right_eye[1]) / 2.0
    width = _face_width(landmarks)
    pitch = (eye_line_y - nose[1]) / (width / 2.0)
    return float(np.clip(pitch * 1.6, -1.0, 1.0))


def _head_roll(landmarks: np.ndarray) -> float:
    """Roll from the angle of the eye line."""
    left = landmarks[LANDMARK_LEFT_EYE_OUTER]
    right = landmarks[LANDMARK_RIGHT_EYE_OUTER]
    dy = float(left[1] - right[1])
    dx = float(left[0] - right[0]) or 1e-6
    angle = math.atan2(dy, dx)
    # Normalise against pi/2 so a 90° roll saturates at ±1
    return float(np.clip(angle / (math.pi / 2.0), -1.0, 1.0))


def _eye_open(
    landmarks: np.ndarray, top_idx: int, bottom_idx: int,
) -> float:
    """Eye openness in ``[0, 1]`` from the vertical lid distance,
    normalised against face width."""
    top = landmarks[top_idx]
    bottom = landmarks[bottom_idx]
    distance = float(abs(top[1] - bottom[1]))
    width = _face_width(landmarks)
    norm = distance / max(width, 1e-6)
    if norm <= _EYE_CLOSED_THRESHOLD:
        return 0.0
    if norm >= _EYE_OPEN_THRESHOLD:
        return 1.0
    span = max(_EYE_OPEN_THRESHOLD - _EYE_CLOSED_THRESHOLD, 1e-9)
    return (norm - _EYE_CLOSED_THRESHOLD) / span


def _mouth_open(landmarks: np.ndarray) -> float:
    top = landmarks[LANDMARK_MOUTH_TOP]
    bottom = landmarks[LANDMARK_MOUTH_BOTTOM]
    distance = float(abs(top[1] - bottom[1]))
    width = _face_width(landmarks)
    return float(np.clip(distance / max(_MOUTH_OPEN_CEILING * width, 1e-6), 0.0, 1.0))
