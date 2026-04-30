"""Tests for the brush input stabiliser."""
from __future__ import annotations

import math

import pytest

from Imervue.paint.stabilizer import (
    STRENGTH_MAX,
    STRENGTH_MIN,
    StrokeStabilizer,
)


# ---------------------------------------------------------------------------
# Construction / strength clamping
# ---------------------------------------------------------------------------


def test_strength_zero_yields_alpha_one():
    s = StrokeStabilizer(0.0)
    assert s.alpha == pytest.approx(1.0)


def test_strength_clamped_below_zero():
    s = StrokeStabilizer(-2.0)
    assert s.alpha == pytest.approx(1.0)


def test_strength_clamped_above_practical_max():
    s = StrokeStabilizer(2.0)
    # Practical cap is 0.95 → alpha 0.05.
    assert s.alpha == pytest.approx(0.05, abs=1e-6)


# ---------------------------------------------------------------------------
# begin / step
# ---------------------------------------------------------------------------


def test_begin_returns_input_unchanged():
    s = StrokeStabilizer(0.5)
    assert s.begin(10.0, 20.0) == (10.0, 20.0)


def test_step_with_zero_strength_passes_through():
    s = StrokeStabilizer(0.0)
    s.begin(0, 0)
    out = s.step(5, 7)
    assert out == (5.0, 7.0)


def test_step_with_strength_lags_behind_input():
    s = StrokeStabilizer(0.5)
    s.begin(0, 0)
    out = s.step(10, 0)
    # alpha=0.5 → smoothed sits halfway to the input.
    assert out[0] == pytest.approx(5.0)
    assert out[1] == pytest.approx(0.0)


def test_step_called_before_begin_seeds_at_first_point():
    s = StrokeStabilizer(0.5)
    out = s.step(7, 9)
    assert out == (7.0, 9.0)


def test_step_smooths_zigzag_noise_into_monotonic_run():
    """A zigzag input (alternating x) should produce a smoothed output
    whose differences shrink over time."""
    s = StrokeStabilizer(0.7)
    s.begin(0.0, 0.0)
    raw = [(0, 0), (10, 0), (0, 0), (10, 0), (0, 0)]
    smoothed = [s.step(*p) for p in raw]
    # Compare amplitude of oscillation: max(|smoothed_x_i - smoothed_x_{i-1}|)
    # should be smaller than the raw zigzag amplitude (10 px).
    deltas = [abs(smoothed[i][0] - smoothed[i - 1][0])
              for i in range(1, len(smoothed))]
    assert max(deltas) < 10.0


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------


def test_flush_with_zero_strength_returns_one_point_at_target():
    s = StrokeStabilizer(0.0)
    s.begin(0, 0)
    out = s.flush(10, 20)
    assert out == [(10.0, 20.0)]


def test_flush_with_strength_drains_toward_target():
    s = StrokeStabilizer(0.7)
    s.begin(0, 0)
    s.step(10, 0)
    out = s.flush(10, 0)
    assert out, "flush should emit at least one point"
    last = out[-1]
    # Last drained point exactly hits the target.
    assert last == (10.0, 0.0)


def test_flush_emits_intermediate_points_for_high_strength():
    s = StrokeStabilizer(0.9)
    s.begin(0, 0)
    s.step(100, 0)   # smoothed lags far behind
    out = s.flush(100, 0)
    # Multiple intermediate points before hitting the target.
    assert len(out) > 2


def test_flush_before_begin_seeds_at_target():
    s = StrokeStabilizer(0.5)
    out = s.flush(5, 5)
    assert out == [(5.0, 5.0)]


def test_flush_stops_within_tolerance():
    s = StrokeStabilizer(0.5)
    s.begin(0, 0)
    s.step(10, 0)   # smoothed at (5, 0)
    out = s.flush(10, 0)
    # We always finish exactly on the target, so the last point matches.
    assert math.isclose(out[-1][0], 10.0, abs_tol=1e-6)


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_strength_min_max_constants():
    assert STRENGTH_MIN == 0.0
    assert STRENGTH_MAX == 1.0
