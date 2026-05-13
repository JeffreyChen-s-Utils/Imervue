"""Tests for the FaceMesh-landmark → puppet-parameter mapper.

Pure-numpy — fabricates synthetic landmark arrays so we don't need
mediapipe / a real webcam in CI.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.puppet.face_landmark_mapper import (
    LANDMARK_LEFT_EYE_BOTTOM,
    LANDMARK_LEFT_EYE_OUTER,
    LANDMARK_LEFT_EYE_TOP,
    LANDMARK_LEFT_TEMPLE,
    LANDMARK_MOUTH_BOTTOM,
    LANDMARK_MOUTH_TOP,
    LANDMARK_NOSE_TIP,
    LANDMARK_RIGHT_EYE_BOTTOM,
    LANDMARK_RIGHT_EYE_OUTER,
    LANDMARK_RIGHT_EYE_TOP,
    LANDMARK_RIGHT_TEMPLE,
    landmarks_to_params,
)


def _neutral_face() -> np.ndarray:
    """Build a 478-landmark array shaped like a neutral, forward-
    facing face. Coordinates roughly in [0, 1] like mediapipe outputs."""
    arr = np.zeros((478, 3), dtype=np.float64)
    # Temple width 0.6 horizontally, eye line at y = 0.4
    arr[LANDMARK_LEFT_TEMPLE] = (0.7, 0.5, 0.0)
    arr[LANDMARK_RIGHT_TEMPLE] = (0.3, 0.5, 0.0)
    arr[LANDMARK_NOSE_TIP] = (0.5, 0.55, -0.05)
    # Eyes: mid points, neutral open distance ~0.025 (between thresholds)
    arr[LANDMARK_LEFT_EYE_OUTER] = (0.65, 0.4, 0.0)
    arr[LANDMARK_LEFT_EYE_TOP] = (0.62, 0.385, 0.0)
    arr[LANDMARK_LEFT_EYE_BOTTOM] = (0.62, 0.41, 0.0)
    arr[LANDMARK_RIGHT_EYE_OUTER] = (0.35, 0.4, 0.0)
    arr[LANDMARK_RIGHT_EYE_TOP] = (0.38, 0.385, 0.0)
    arr[LANDMARK_RIGHT_EYE_BOTTOM] = (0.38, 0.41, 0.0)
    arr[LANDMARK_MOUTH_TOP] = (0.5, 0.7, 0.0)
    arr[LANDMARK_MOUTH_BOTTOM] = (0.5, 0.71, 0.0)
    return arr


def test_neutral_face_yaw_pitch_near_zero():
    out = landmarks_to_params(_neutral_face())
    assert abs(out["ParamAngleX"]) < 0.05
    assert abs(out["ParamAngleZ"]) < 0.05


def test_yaw_positive_when_nose_offset_right():
    arr = _neutral_face()
    arr[LANDMARK_NOSE_TIP] = (0.62, 0.55, -0.05)   # nose pulled right
    out = landmarks_to_params(arr)
    assert out["ParamAngleX"] > 0.2


def test_yaw_saturates_at_unit_value():
    arr = _neutral_face()
    arr[LANDMARK_NOSE_TIP] = (1.5, 0.55, -0.05)   # cursor way off-screen
    out = landmarks_to_params(arr)
    assert out["ParamAngleX"] == pytest.approx(1.0)


def test_eye_open_near_zero_for_closed_eye():
    arr = _neutral_face()
    arr[LANDMARK_LEFT_EYE_TOP] = (0.62, 0.40, 0.0)
    arr[LANDMARK_LEFT_EYE_BOTTOM] = (0.62, 0.40, 0.0)   # zero gap
    out = landmarks_to_params(arr)
    assert out["ParamEyeLOpen"] == pytest.approx(0.0)


def test_eye_open_max_for_wide_open_eye():
    arr = _neutral_face()
    arr[LANDMARK_LEFT_EYE_TOP] = (0.62, 0.35, 0.0)
    arr[LANDMARK_LEFT_EYE_BOTTOM] = (0.62, 0.45, 0.0)   # large gap > threshold
    out = landmarks_to_params(arr)
    assert out["ParamEyeLOpen"] == pytest.approx(1.0)


def test_mouth_open_high_for_yawning_face():
    arr = _neutral_face()
    arr[LANDMARK_MOUTH_TOP] = (0.5, 0.65, 0.0)
    arr[LANDMARK_MOUTH_BOTTOM] = (0.5, 0.75, 0.0)
    out = landmarks_to_params(arr)
    assert out["ParamMouthOpenY"] > 0.5


def test_malformed_input_returns_empty_dict():
    # Only 100 landmarks instead of 468 → reject
    bad = np.zeros((100, 3), dtype=np.float64)
    assert landmarks_to_params(bad) == {}
    # Missing third dimension is OK (only x, y used) but shape (478,) flat is not
    flat = np.zeros((478,), dtype=np.float64)
    assert landmarks_to_params(flat) == {}


def test_roll_responds_to_eye_line_tilt():
    """The roll value flips sign with the eye-line tilt direction; the
    exact sign depends on image-y convention, but both a tilt in either
    direction should be far from zero."""
    arr = _neutral_face()
    arr[LANDMARK_LEFT_EYE_OUTER] = (0.65, 0.30, 0.0)
    arr[LANDMARK_RIGHT_EYE_OUTER] = (0.35, 0.50, 0.0)
    tilted = landmarks_to_params(arr)
    arr[LANDMARK_LEFT_EYE_OUTER] = (0.65, 0.50, 0.0)
    arr[LANDMARK_RIGHT_EYE_OUTER] = (0.35, 0.30, 0.0)
    other = landmarks_to_params(arr)
    assert abs(tilted["ParamAngleZ"]) > 0.1
    # Sign flips when the tilt direction flips
    assert tilted["ParamAngleZ"] * other["ParamAngleZ"] < 0
