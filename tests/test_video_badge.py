"""Tests for the ▶ video badge geometry helper."""
from __future__ import annotations

import math

import pytest

from Imervue.gpu_image_view.video_badge import (
    VideoBadge,
    video_badge_geometry,
    video_badge_radius,
)


# ---------------------------------------------------------------------------
# video_badge_radius — sizing + clamping
# ---------------------------------------------------------------------------


def test_radius_uses_shorter_side():
    # Wide tile: 200x50 -> shorter side 50 -> 50 * 0.16 = 8 -> clamped up to min 9.
    assert video_badge_radius(200, 50) == 9.0


def test_radius_scales_with_size():
    # 100 px shorter side -> 16 px, inside the clamp band.
    assert video_badge_radius(100, 120) == 16.0


def test_radius_clamped_to_min():
    assert video_badge_radius(10, 10) == 9.0


def test_radius_clamped_to_max():
    assert video_badge_radius(5000, 4000) == 30.0


def test_radius_ignores_sign():
    assert video_badge_radius(-100, -120) == 16.0


# ---------------------------------------------------------------------------
# video_badge_geometry
# ---------------------------------------------------------------------------


def test_centre_is_midpoint():
    badge = video_badge_geometry(0, 0, 100, 200)
    assert badge.cx == 50.0
    assert badge.cy == 100.0


def test_returns_dataclass_with_three_triangle_points():
    badge = video_badge_geometry(0, 0, 100, 100)
    assert isinstance(badge, VideoBadge)
    assert len(badge.triangle) == 3


def test_triangle_tip_is_rightmost_and_centred_vertically():
    badge = video_badge_geometry(0, 0, 120, 120)
    tip, top, bottom = badge.triangle
    assert tip[0] > top[0]
    assert tip[0] > bottom[0]
    assert tip[1] == badge.cy


def test_triangle_back_edge_is_symmetric():
    badge = video_badge_geometry(0, 0, 120, 120)
    _tip, top, bottom = badge.triangle
    assert top[0] == bottom[0]
    # top and bottom straddle the centre line symmetrically.
    assert (top[1] + bottom[1]) / 2.0 == pytest.approx(badge.cy)
    assert top[1] < badge.cy < bottom[1]


def test_all_triangle_points_inside_disc():
    badge = video_badge_geometry(10, 20, 210, 180)
    for vx, vy in badge.triangle:
        dist = math.hypot(vx - badge.cx, vy - badge.cy)
        assert dist <= badge.radius
