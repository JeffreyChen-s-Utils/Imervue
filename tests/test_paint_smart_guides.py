"""Tests for smart guides + snapping."""
from __future__ import annotations

import dataclasses

import pytest

from Imervue.paint.smart_guides import (
    SNAP_KINDS,
    SnapTarget,
    snap_point,
    snap_rect,
    targets_from_rect,
)


# ---------------------------------------------------------------------------
# SnapTarget
# ---------------------------------------------------------------------------


def test_snap_kinds_set():
    assert set(SNAP_KINDS) == {"vertical", "horizontal"}


def test_snap_target_construction():
    t = SnapTarget(kind="vertical", position=100.0, label="layer left")
    assert t.position == pytest.approx(100.0)


def test_snap_target_is_frozen():
    t = SnapTarget(kind="vertical", position=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.position = 5.0  # type: ignore[misc]


def test_snap_target_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown snap kind"):
        SnapTarget(kind="diagonal", position=0.0)


# ---------------------------------------------------------------------------
# snap_point
# ---------------------------------------------------------------------------


def test_snap_point_inside_threshold_snaps_to_target():
    targets = [SnapTarget(kind="vertical", position=100.0)]
    (sx, sy), activated = snap_point((104.0, 50.0), targets)
    assert sx == pytest.approx(100.0)
    assert sy == pytest.approx(50.0)
    assert len(activated) == 1


def test_snap_point_outside_threshold_does_not_snap():
    targets = [SnapTarget(kind="vertical", position=100.0)]
    (sx, _), activated = snap_point((150.0, 50.0), targets, threshold_px=8)
    assert sx == pytest.approx(150.0)
    assert activated == []


def test_snap_point_picks_nearest_target_per_axis():
    targets = [
        SnapTarget(kind="vertical", position=100.0),
        SnapTarget(kind="vertical", position=120.0),
    ]
    (sx, _sy), _ = snap_point((118.0, 50.0), targets)
    # 118 is 2 away from 120 and 18 away from 100 — picks 120.
    assert sx == pytest.approx(120.0)


def test_snap_point_axes_independent():
    targets = [
        SnapTarget(kind="vertical", position=100.0),
        SnapTarget(kind="horizontal", position=50.0),
    ]
    (sx, sy), activated = snap_point((104.0, 53.0), targets)
    assert sx == pytest.approx(100.0)
    assert sy == pytest.approx(50.0)
    assert len(activated) == 2


def test_snap_point_only_horizontal_target_leaves_x_unchanged():
    targets = [SnapTarget(kind="horizontal", position=50.0)]
    (sx, sy), _ = snap_point((104.0, 53.0), targets)
    assert sx == pytest.approx(104.0)
    assert sy == pytest.approx(50.0)


def test_snap_point_threshold_zero_only_snaps_at_exact_match():
    targets = [SnapTarget(kind="vertical", position=100.0)]
    (sx, _sy), activated = snap_point(
        (100.0, 0.0), targets, threshold_px=0,
    )
    assert sx == pytest.approx(100.0)
    assert len(activated) == 1


def test_snap_point_negative_threshold_raises():
    with pytest.raises(ValueError, match="threshold_px"):
        snap_point((0, 0), [], threshold_px=-1)


def test_snap_point_empty_targets_returns_input():
    (sx, sy), activated = snap_point((10.0, 20.0), [])
    assert sx == pytest.approx(10.0)
    assert sy == pytest.approx(20.0)
    assert activated == []


# ---------------------------------------------------------------------------
# snap_rect
# ---------------------------------------------------------------------------


def test_snap_rect_left_edge_snaps_to_vertical_target():
    rect = (104.0, 50.0, 50.0, 50.0)
    targets = [SnapTarget(kind="vertical", position=100.0)]
    (snapped, activated) = snap_rect(rect, targets)
    assert snapped[0] == pytest.approx(100.0)   # left edge moved
    assert snapped[1] == pytest.approx(50.0)    # y unchanged
    assert snapped[2] == pytest.approx(50.0)    # width preserved
    assert snapped[3] == pytest.approx(50.0)    # height preserved
    assert len(activated) == 1


def test_snap_rect_centre_snaps():
    """Rect at x=100 width 50 has centre at 125; snap target at 130
    should pull it via centre snap (offset 5)."""
    rect = (100.0, 0.0, 50.0, 50.0)
    targets = [SnapTarget(kind="vertical", position=130.0)]
    (snapped, _) = snap_rect(rect, targets)
    assert snapped[0] == pytest.approx(105.0)   # 100 + 5 (centre 125 → 130)


def test_snap_rect_right_edge_snaps():
    rect = (50.0, 0.0, 40.0, 50.0)
    # Right edge currently at 90; snap at 95 (delta +5).
    targets = [SnapTarget(kind="vertical", position=95.0)]
    (snapped, _) = snap_rect(rect, targets)
    assert snapped[0] == pytest.approx(55.0)


def test_snap_rect_picks_smallest_offset():
    """Two targets, one closer to left edge, one closer to right edge —
    the smaller offset wins."""
    rect = (100.0, 0.0, 50.0, 50.0)
    targets = [
        # Left edge 100; target at 95 → distance 5.
        SnapTarget(kind="vertical", position=95.0, label="far"),
        # Right edge 150; target at 152 → distance 2.
        SnapTarget(kind="vertical", position=152.0, label="near"),
    ]
    (snapped, activated) = snap_rect(rect, targets)
    # Snap should use the +2 offset, not -5.
    assert snapped[0] == pytest.approx(102.0)
    assert activated[0].label == "near"


def test_snap_rect_negative_threshold_raises():
    with pytest.raises(ValueError, match="threshold_px"):
        snap_rect((0, 0, 10, 10), [], threshold_px=-1)


def test_snap_rect_no_targets_unchanged():
    rect = (10.0, 20.0, 30.0, 40.0)
    (snapped, activated) = snap_rect(rect, [])
    assert snapped == rect
    assert activated == []


# ---------------------------------------------------------------------------
# targets_from_rect
# ---------------------------------------------------------------------------


def test_targets_from_rect_yields_six_entries():
    targets = targets_from_rect((0.0, 0.0, 100.0, 60.0))
    assert len(targets) == 6


def test_targets_from_rect_kinds_balanced():
    targets = targets_from_rect((0.0, 0.0, 100.0, 60.0))
    verticals = [t for t in targets if t.kind == "vertical"]
    horizontals = [t for t in targets if t.kind == "horizontal"]
    assert len(verticals) == 3
    assert len(horizontals) == 3


def test_targets_from_rect_labels_use_prefix():
    targets = targets_from_rect((0.0, 0.0, 100.0, 60.0), label_prefix="layer 1")
    labels = {t.label for t in targets}
    assert "layer 1 left" in labels
    assert "layer 1 right" in labels
    assert "layer 1 top" in labels
    assert "layer 1 bottom" in labels
