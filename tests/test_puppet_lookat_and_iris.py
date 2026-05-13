"""Tests for cursor look-at eyeball params + webcam iris tracking."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.puppet.face_landmark_mapper import landmarks_to_params
from Imervue.puppet.input_drivers import (
    DEFAULT_DRAG_EYE_X_PARAM,
    DEFAULT_DRAG_EYE_Y_PARAM,
    DEFAULT_DRAG_X_PARAM,
    cursor_to_angle_params,
)


# ---------------------------------------------------------------------------
# cursor_to_angle_params now also yields eyeball params
# ---------------------------------------------------------------------------


def test_cursor_at_centre_eyeballs_are_zero():
    out = cursor_to_angle_params(50.0, 50.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_EYE_X_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_DRAG_EYE_Y_PARAM] == pytest.approx(0.0)


def test_eyeballs_lead_head_at_intermediate_cursor():
    """A cursor 30% past centre puts the head at 0.6 (norm × 2) but
    the eyes go further (gain 1.5) before clamping."""
    out = cursor_to_angle_params(65.0, 50.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(0.3, abs=1e-3)
    assert out[DEFAULT_DRAG_EYE_X_PARAM] == pytest.approx(0.45, abs=1e-3)


def test_eyeballs_saturate_before_head():
    """At cursor 70% past centre, the head is at 0.7 but eyes saturate."""
    out = cursor_to_angle_params(85.0, 50.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(0.7, abs=1e-3)
    assert out[DEFAULT_DRAG_EYE_X_PARAM] == pytest.approx(1.0)


def test_eyeballs_zero_when_canvas_is_zero():
    out = cursor_to_angle_params(50.0, 50.0, 0.0, 0.0)
    assert out[DEFAULT_DRAG_EYE_X_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_DRAG_EYE_Y_PARAM] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Webcam iris tracking
# ---------------------------------------------------------------------------


def _make_landmarks_with_iris(
    iris_offset_x: float = 0.0,
    iris_offset_y: float = 0.0,
) -> np.ndarray:
    """Build a synthetic 478-landmark array where the iris centres
    sit at the eye-box midpoint plus the supplied offset. Other
    landmarks at zero — the mapper only reads the eye corners + iris
    for these tests."""
    arr = np.zeros((478, 3), dtype=np.float64)
    # Right eye box: outer (33) at x=-0.1, inner (133) at x=-0.05.
    # Top (159) at y=-0.05, bottom (145) at y=0.0.
    arr[33] = (-0.1, -0.02, 0.0)
    arr[133] = (-0.05, -0.02, 0.0)
    arr[159] = (-0.075, -0.05, 0.0)
    arr[145] = (-0.075, 0.0, 0.0)
    # Left eye box (mirror): outer (263) at x=0.1, inner (362) at x=0.05.
    arr[263] = (0.1, -0.02, 0.0)
    arr[362] = (0.05, -0.02, 0.0)
    arr[386] = (0.075, -0.05, 0.0)
    arr[374] = (0.075, 0.0, 0.0)
    # Iris centres at midpoint + offset.
    arr[468] = (-0.075 + iris_offset_x, -0.025 + iris_offset_y, 0.0)
    arr[473] = (0.075 + iris_offset_x, -0.025 + iris_offset_y, 0.0)
    # Temples (234 / 454) for face-width — needed by some other params.
    arr[234] = (-0.2, 0.0, 0.0)
    arr[454] = (0.2, 0.0, 0.0)
    # Nose tip (4) at centre.
    arr[4] = (0.0, 0.0, 0.0)
    # Mouth points so _mouth_open doesn't divide by zero.
    arr[13] = (0.0, -0.01, 0.0)
    arr[14] = (0.0, 0.01, 0.0)
    return arr


def test_landmarks_to_params_emits_eyeball_when_iris_present():
    out = landmarks_to_params(_make_landmarks_with_iris())
    assert "ParamEyeBallX" in out
    assert "ParamEyeBallY" in out


def test_eyeball_zero_when_iris_centred():
    out = landmarks_to_params(_make_landmarks_with_iris(0.0, 0.0))
    assert out["ParamEyeBallX"] == pytest.approx(0.0, abs=1e-3)
    assert out["ParamEyeBallY"] == pytest.approx(0.0, abs=1e-3)


def test_eyeball_x_positive_when_iris_shifted_right():
    """Iris shift in +x direction (right in image) → ParamEyeBallX > 0."""
    out = landmarks_to_params(_make_landmarks_with_iris(iris_offset_x=0.01))
    assert out["ParamEyeBallX"] > 0.5


def test_eyeball_x_negative_when_iris_shifted_left():
    out = landmarks_to_params(_make_landmarks_with_iris(iris_offset_x=-0.01))
    assert out["ParamEyeBallX"] < -0.5


def test_eyeball_y_positive_when_iris_shifted_up():
    """Image space is y-down, so iris shifted -y means looking up,
    which should be ParamEyeBallY > 0 (Cubism convention)."""
    out = landmarks_to_params(_make_landmarks_with_iris(iris_offset_y=-0.01))
    assert out["ParamEyeBallY"] > 0.5


def test_no_eyeball_emitted_when_landmarks_below_478():
    """Mediapipe FaceMesh without refine_landmarks returns 468 points
    — no iris info available, so the mapper must not invent values."""
    short = _make_landmarks_with_iris()[:468]
    out = landmarks_to_params(short)
    assert "ParamEyeBallX" not in out
    assert "ParamEyeBallY" not in out
