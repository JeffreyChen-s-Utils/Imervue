"""Tests for the puppet easing-preset library."""
from __future__ import annotations

import pytest

from Imervue.puppet.easing import (
    EASING_NAMES,
    control_points_for_segment,
    ease_value,
    easing_bezier,
)


def _curve(name: str, steps: int = 40) -> list[float]:
    return [ease_value(name, i / steps) for i in range(steps + 1)]


def _is_monotone_increasing(values: list[float]) -> bool:
    return all(b >= a - 1e-9 for a, b in zip(values, values[1:], strict=False))


# ---------------------------------------------------------------------------
# ease_value
# ---------------------------------------------------------------------------


def test_linear_is_identity():
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert ease_value("linear", u) == pytest.approx(u)


def test_every_easing_pins_its_endpoints():
    for name in EASING_NAMES:
        assert ease_value(name, 0.0) == pytest.approx(0.0, abs=1e-9)
        assert ease_value(name, 1.0) == pytest.approx(1.0, abs=1e-9)


def test_known_polynomial_values():
    assert ease_value("ease-in-cubic", 0.5) == pytest.approx(0.125)
    assert ease_value("ease-out-cubic", 0.5) == pytest.approx(0.875)
    assert ease_value("ease-in-quad", 0.5) == pytest.approx(0.25)
    assert ease_value("ease-in-out-quad", 0.25) == pytest.approx(0.125)


def test_progress_is_clamped():
    assert ease_value("ease-in-quad", -1.0) == pytest.approx(0.0)
    assert ease_value("ease-in-quad", 2.0) == pytest.approx(1.0)


@pytest.mark.parametrize("name", [
    "ease-in-cubic", "ease-out-sine", "ease-in-out-quint", "ease-in-expo",
])
def test_monotone_families_increase(name):
    assert _is_monotone_increasing(_curve(name))


def test_back_overshoots_and_undershoots():
    assert max(_curve("ease-out-back")) > 1.0
    assert min(_curve("ease-in-back")) < 0.0


def test_elastic_oscillates():
    values = _curve("ease-out-elastic")
    assert any(b < a - 1e-6 for a, b in zip(values, values[1:], strict=False))


def test_bounce_settles_at_one_after_bouncing():
    assert ease_value("ease-out-bounce", 1.0) == pytest.approx(1.0)
    values = _curve("ease-out-bounce")
    assert any(b < a - 1e-6 for a, b in zip(values, values[1:], strict=False))


def test_unknown_easing_raises():
    with pytest.raises(ValueError, match="unknown easing"):
        ease_value("ease-in-wobble", 0.5)


# ---------------------------------------------------------------------------
# bezier handles
# ---------------------------------------------------------------------------


def test_easing_bezier_returns_handles():
    assert easing_bezier("ease-in-cubic") == (0.32, 0.0, 0.67, 0.0)
    assert easing_bezier("linear") == (0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("name", ["ease-out-elastic", "ease-in-bounce"])
def test_oscillating_easings_have_no_single_bezier(name):
    with pytest.raises(ValueError, match="no single cubic-bezier"):
        easing_bezier(name)


# ---------------------------------------------------------------------------
# control_points_for_segment
# ---------------------------------------------------------------------------


def test_control_points_scale_onto_segment():
    c0, c1 = control_points_for_segment("ease-in-cubic", (0.0, 0.0), (2.0, 10.0))
    # handles (0.32, 0, 0.67, 0): times scale by 2, values by 10.
    assert c0 == pytest.approx((0.64, 0.0))
    assert c1 == pytest.approx((1.34, 0.0))


def test_control_points_offset_by_start():
    c0, c1 = control_points_for_segment("linear", (1.0, 5.0), (3.0, 5.0))
    assert c0 == pytest.approx((1.0, 5.0))
    assert c1 == pytest.approx((3.0, 5.0))


def test_control_points_unknown_raises():
    with pytest.raises(ValueError):
        control_points_for_segment("ease-out-elastic", (0.0, 0.0), (1.0, 1.0))


# ---------------------------------------------------------------------------
# Integration: the handles drive a real cubic-bezier MotionSegment
# ---------------------------------------------------------------------------


def test_bezier_segment_samples_a_monotone_eased_curve():
    from Imervue.puppet import motion_sampler
    from Imervue.puppet.document import MotionSegment

    c0, c1 = control_points_for_segment("ease-in-out-quad", (0.0, 0.0), (1.0, 1.0))
    seg = MotionSegment(
        type="cubic-bezier", p0=(0.0, 0.0), p1=(1.0, 1.0), c0=c0, c1=c1,
    )
    samples = [motion_sampler._sample_segment(seg, t / 10) for t in range(11)]
    assert samples[0] == pytest.approx(0.0, abs=1e-6)
    assert samples[-1] == pytest.approx(1.0, abs=1e-6)
    assert _is_monotone_increasing(samples)
