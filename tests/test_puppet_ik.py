"""Tests for the analytic two-bone IK solver.

Pure trigonometry — no Qt/GL, so no headless-CI skip. The core check is a
round-trip: solving for a reachable target and running the result back through
forward kinematics must land the tip on the target.
"""
from __future__ import annotations

import math

import pytest

from Imervue.puppet.ik import (
    forward_two_bone,
    solve_two_bone_ik,
    two_bone_ik_angles,
)


def _reaches(root, l1, l2, target, *, flip=False):
    a1, a2 = solve_two_bone_ik(root, l1, l2, target, flip=flip)
    return forward_two_bone(root, l1, l2, a1, a2)


class TestSolveTwoBoneIk:
    @pytest.mark.parametrize("target", [(1.0, 1.0), (1.5, 0.3), (0.2, 1.4), (-1.0, 0.5)])
    def test_reachable_target_is_hit(self, target):
        tip = _reaches((0.0, 0.0), 1.0, 1.0, target)
        assert tip == pytest.approx(target, abs=1e-9)

    def test_both_elbow_solutions_reach_the_target(self):
        target = (1.0, 1.0)
        assert _reaches((0.0, 0.0), 1.0, 1.0, target) == pytest.approx(target, abs=1e-9)
        assert _reaches((0.0, 0.0), 1.0, 1.0, target, flip=True) == pytest.approx(
            target, abs=1e-9)

    def test_asymmetric_segments_reach_target(self):
        tip = _reaches((2.0, -1.0), 1.5, 0.7, (3.0, 0.2))
        assert tip == pytest.approx((3.0, 0.2), abs=1e-9)

    def test_over_reach_clamps_to_full_extension(self):
        # Target at distance 3 with reach 2 → tip at the 2-unit extreme, in line.
        tip = _reaches((0.0, 0.0), 1.0, 1.0, (3.0, 0.0))
        assert tip == pytest.approx((2.0, 0.0), abs=1e-9)

    def test_under_reach_clamps_to_inner_radius(self):
        # l1=2, l2=1 can't fold tighter than radius 1; target at 0.5 → tip at 1.
        tip = _reaches((0.0, 0.0), 2.0, 1.0, (0.5, 0.0))
        assert tip == pytest.approx((1.0, 0.0), abs=1e-9)

    def test_target_at_root_does_not_crash(self):
        a1, a2 = solve_two_bone_ik((0.0, 0.0), 1.0, 1.0, (0.0, 0.0))
        assert math.isfinite(a1) and math.isfinite(a2)

    def test_zero_length_first_bone_is_safe(self):
        a1, a2 = solve_two_bone_ik((0.0, 0.0), 0.0, 1.0, (0.5, 0.0))
        assert math.isfinite(a1) and math.isfinite(a2)


class TestTwoBoneIkAngles:
    def test_returns_angle_per_bone(self):
        angles = two_bone_ik_angles("upper", "lower", (0.0, 0.0), 1.0, 1.0, (1.0, 1.0))
        assert set(angles) == {"upper", "lower"}
        tip = forward_two_bone((0.0, 0.0), 1.0, 1.0, angles["upper"], angles["lower"])
        assert tip == pytest.approx((1.0, 1.0), abs=1e-9)
