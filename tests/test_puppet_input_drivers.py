"""Pure-Python tests for the input mappers — no Qt or audio fixtures."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.puppet.input_drivers import (
    DEFAULT_DRAG_X_PARAM,
    DEFAULT_DRAG_Y_PARAM,
    audio_rms_to_mouth,
    blink_curve_value,
    cursor_to_angle_params,
)


# ---------------------------------------------------------------------------
# cursor_to_angle_params
# ---------------------------------------------------------------------------


def test_cursor_at_centre_yields_zero_angles():
    out = cursor_to_angle_params(50.0, 50.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(0.0)
    assert out[DEFAULT_DRAG_Y_PARAM] == pytest.approx(0.0)


def test_cursor_at_edges_saturates_at_unit_value():
    out = cursor_to_angle_params(100.0, 100.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(1.0)
    assert out[DEFAULT_DRAG_Y_PARAM] == pytest.approx(1.0)
    out = cursor_to_angle_params(0.0, 0.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(-1.0)


def test_cursor_outside_canvas_clamps():
    out = cursor_to_angle_params(500.0, 500.0, 100.0, 100.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(1.0)
    assert out[DEFAULT_DRAG_Y_PARAM] == pytest.approx(1.0)


def test_cursor_with_zero_canvas_returns_zero():
    out = cursor_to_angle_params(50.0, 50.0, 0.0, 0.0)
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(0.0)


def test_sensitivity_amplifies_motion():
    out = cursor_to_angle_params(75.0, 50.0, 100.0, 100.0, sensitivity=2.0)
    # Cursor at 75 of 100 → norm 0.5, ×2 sensitivity → 1.0
    assert out[DEFAULT_DRAG_X_PARAM] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# blink_curve_value
# ---------------------------------------------------------------------------


def test_blink_at_zero_starts_closed_then_opens():
    """At elapsed = 0 the eye is at the start of the cycle's closing
    sweep. Must return values in [0, 1] and reach 0 mid-blink."""
    duration = 0.2
    open_at_zero = blink_curve_value(0.0, interval=4.0, duration=duration)
    half_blink = blink_curve_value(duration / 2, interval=4.0, duration=duration)
    end_blink = blink_curve_value(duration, interval=4.0, duration=duration)
    # cosine close→open → 1 at start, 0 at midpoint, 1 at end (snap-back to open)
    assert open_at_zero == pytest.approx(1.0, abs=1e-3)
    assert half_blink == pytest.approx(0.0, abs=1e-3)
    assert end_blink == pytest.approx(1.0, abs=1e-3)


def test_blink_open_outside_blink_window():
    duration = 0.2
    interval = 4.0
    # Mid-cycle outside the blink window → fully open
    assert blink_curve_value(2.0, interval=interval, duration=duration) == 1.0


def test_blink_loops_with_interval():
    duration = 0.2
    interval = 4.0
    a = blink_curve_value(0.05, interval=interval, duration=duration)
    b = blink_curve_value(interval + 0.05, interval=interval, duration=duration)
    assert a == pytest.approx(b)


def test_blink_invalid_inputs_return_open():
    assert blink_curve_value(0.5, interval=0, duration=0.2) == 1.0
    assert blink_curve_value(0.5, interval=4.0, duration=0) == 1.0


# ---------------------------------------------------------------------------
# audio_rms_to_mouth
# ---------------------------------------------------------------------------


def test_silence_returns_zero():
    arr = np.zeros(1024, dtype=np.float32)
    assert audio_rms_to_mouth(arr) == 0.0


def test_loud_signal_saturates_at_one():
    arr = np.full(1024, 0.9, dtype=np.float32)
    assert audio_rms_to_mouth(arr) == pytest.approx(1.0)


def test_midrange_lerps_linearly():
    # Noise with RMS ~ 0.1, between floor 0.005 and ceiling 0.2
    arr = np.full(1024, 0.1, dtype=np.float32)
    # |signal| = 0.1, RMS = 0.1 → (0.1 - 0.005) / (0.2 - 0.005) ≈ 0.487
    assert audio_rms_to_mouth(arr) == pytest.approx(0.487, abs=1e-2)


def test_int16_input_normalised_correctly():
    # Half-scale int16 → 0.5 RMS in float32
    arr = np.full(1024, 16384, dtype=np.int16)
    out = audio_rms_to_mouth(arr)
    assert out == pytest.approx(1.0)   # well above ceiling


def test_bytes_input_decoded_as_int16():
    arr = np.full(1024, 8192, dtype=np.int16)   # 0.25 RMS
    raw = arr.tobytes()
    out = audio_rms_to_mouth(raw)
    assert out > 0.5   # well into the linear range


def test_empty_input_returns_zero():
    assert audio_rms_to_mouth(np.array([], dtype=np.float32)) == 0.0
