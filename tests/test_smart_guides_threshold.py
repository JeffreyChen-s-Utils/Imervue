"""snap_point must only snap targets within threshold_px, not a pixel past it.

The old ``threshold + 1`` seed with a strict ``<`` accepted distances up to one
pixel beyond the threshold.
"""
from __future__ import annotations

import pytest

from Imervue.paint.smart_guides import SnapTarget, snap_point


def test_target_just_past_threshold_does_not_snap():
    target = SnapTarget(kind="vertical", position=12.5)   # 2.5px from x=10
    (sx, _sy), activated = snap_point((10.0, 10.0), [target], threshold_px=2)
    assert sx == pytest.approx(10.0)
    assert activated == []


def test_target_at_threshold_snaps():
    target = SnapTarget(kind="vertical", position=12.0)   # exactly 2px away
    (sx, _sy), activated = snap_point((10.0, 10.0), [target], threshold_px=2)
    assert sx == pytest.approx(12.0)
    assert target in activated


def test_closest_target_wins():
    near = SnapTarget(kind="vertical", position=11.0)     # 1px
    far = SnapTarget(kind="vertical", position=12.0)      # 2px
    (sx, _sy), _ = snap_point((10.0, 10.0), [far, near], threshold_px=3)
    assert sx == pytest.approx(11.0)
