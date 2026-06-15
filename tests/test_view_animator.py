"""Tests for the pure easing / transition helpers in ``view_animator``.

These cover the curve math, the fade-in opacity, the transition gate, the
eased-zoom interpolation with anchor pinning, and the momentum-pan decay — all
without a timer or GL context.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.view_animator import (
    animation_progress,
    clamp01,
    decayed_velocity,
    ease_out_cubic,
    eased_zoom,
    fade_opacity,
    image_point_at,
    lerp,
    offset_for_fixed_point,
    should_transition,
    velocity_settled,
)


class TestClamp01:
    @pytest.mark.parametrize("value,expected", [(-1.0, 0.0), (0.5, 0.5), (2.0, 1.0)])
    def test_clamps(self, value, expected):
        assert clamp01(value) == pytest.approx(expected)


class TestEaseOutCubic:
    def test_endpoints(self):
        assert ease_out_cubic(0.0) == pytest.approx(0.0)
        assert ease_out_cubic(1.0) == pytest.approx(1.0)

    def test_decelerates(self):
        # Ease-out is ahead of linear at the midpoint (fast start, slow finish).
        assert ease_out_cubic(0.5) > 0.5

    def test_out_of_range_is_clamped(self):
        assert ease_out_cubic(-1.0) == pytest.approx(0.0)
        assert ease_out_cubic(2.0) == pytest.approx(1.0)


class TestAnimationProgress:
    def test_linear_progress(self):
        assert animation_progress(50, 200) == pytest.approx(0.25)

    def test_clamps_past_end(self):
        assert animation_progress(300, 200) == pytest.approx(1.0)

    def test_non_positive_duration_completes_immediately(self):
        assert animation_progress(0, 0) == pytest.approx(1.0)


class TestFadeOpacity:
    def test_starts_transparent_ends_opaque(self):
        assert fade_opacity(0, 160) == pytest.approx(0.0)
        assert fade_opacity(160, 160) == pytest.approx(1.0)

    def test_is_monotonic(self):
        a = fade_opacity(40, 160)
        b = fade_opacity(80, 160)
        assert 0.0 < a < b < 1.0


class TestShouldTransition:
    def test_enabled_and_idle_plays(self):
        assert should_transition(True, slideshow_running=False) is True

    def test_disabled_never_plays(self):
        assert should_transition(False, slideshow_running=False) is False

    def test_slideshow_running_suppresses(self):
        assert should_transition(True, slideshow_running=True) is False


class TestEasedZoom:
    def test_endpoints(self):
        assert eased_zoom(1.0, 4.0, 0, 120) == pytest.approx(1.0)
        assert eased_zoom(1.0, 4.0, 120, 120) == pytest.approx(4.0)

    def test_midpoint_between_start_and_target(self):
        mid = eased_zoom(1.0, 5.0, 60, 120)
        assert 1.0 < mid < 5.0


class TestAnchorPinning:
    def test_fixed_point_round_trips(self):
        # The image point under a screen anchor must map back to that anchor
        # after the offset is recomputed for any new zoom.
        screen, offset, zoom = 640.0, 100.0, 2.0
        image_point = image_point_at(screen, offset, zoom)
        new_zoom = 5.0
        new_offset = offset_for_fixed_point(screen, image_point, new_zoom)
        assert image_point * new_zoom + new_offset == pytest.approx(screen)

    def test_image_point_at_guards_zero_zoom(self):
        assert image_point_at(640.0, 100.0, 0.0) == pytest.approx(0.0)


class TestMomentum:
    def test_lerp(self):
        assert lerp(0.0, 10.0, 0.3) == pytest.approx(3.0)

    def test_velocity_decays(self):
        assert decayed_velocity(10.0, 0.85) == pytest.approx(8.5)

    def test_settled_below_threshold(self):
        assert velocity_settled(0.2, 0.2, 0.4) is True

    def test_not_settled_above_threshold(self):
        assert velocity_settled(5.0, 0.0, 0.4) is False

    def test_settled_uses_speed_magnitude(self):
        # (0.3, 0.3) → speed² = 0.18 ≤ 0.4² = 0.16? No → not settled.
        assert velocity_settled(0.3, 0.3, 0.4) is False
