"""Tests for the 2D pose skeleton + pose dock."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.pose_skeleton import (
    Bone,
    Joint,
    PoseSkeleton,
    default_skeleton,
    render_skeleton,
)


def test_default_skeleton_has_canonical_joints():
    skel = default_skeleton()
    expected = {
        "head", "neck", "chest", "hips",
        "l_shoulder", "r_shoulder", "l_elbow", "r_elbow",
        "l_wrist", "r_wrist",
        "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle",
    }
    assert set(skel.joints) == expected


def test_default_skeleton_bones_reference_existing_joints():
    skel = default_skeleton()
    names = set(skel.joints)
    for bone in skel.bones:
        assert bone.a in names, f"bone endpoint {bone.a!r} missing"
        assert bone.b in names, f"bone endpoint {bone.b!r} missing"


def test_move_joint_clamps_into_unit_square():
    skel = default_skeleton()
    skel.move_joint("head", -0.5, 1.7)
    head = skel.joint("head")
    assert head.x == pytest.approx(0.0)
    assert head.y == pytest.approx(1.0)


def test_round_trip_through_dict_preserves_joint_positions():
    skel = default_skeleton()
    skel.move_joint("head", 0.4, 0.42)
    raw = skel.to_dict()
    restored = PoseSkeleton.from_dict(raw)
    assert restored.joint("head").x == pytest.approx(0.4)
    assert restored.joint("head").y == pytest.approx(0.42)
    assert len(restored.bones) == len(skel.bones)


def test_render_skeleton_writes_pixels_at_canvas_size():
    skel = default_skeleton()
    arr = render_skeleton(skel, height=100, width=80)
    assert arr.shape == (100, 80, 4)
    assert arr.dtype == np.uint8
    # At least one opaque pixel (the head disc) must hit the buffer.
    assert int(arr[..., 3].max()) > 0


def test_render_skeleton_rejects_zero_size():
    skel = default_skeleton()
    with pytest.raises(ValueError, match="positive"):
        render_skeleton(skel, height=0, width=10)


def test_joint_with_xy_returns_new_instance():
    j = Joint(name="head", x=0.5, y=0.5, radius_px=10)
    moved = j.with_xy(0.4, 0.6)
    assert moved.x == pytest.approx(0.4)
    assert moved.y == pytest.approx(0.6)
    # Original is unchanged because Joint is frozen.
    assert j.x == pytest.approx(0.5)
    assert j.y == pytest.approx(0.5)


def test_skeleton_with_missing_bone_endpoints_renders_quietly():
    """A bone referencing an unknown joint must not crash; just skip."""
    skel = PoseSkeleton(
        joints={"a": Joint("a", 0.1, 0.1)},
        bones=(Bone("a", "ghost"),),
    )
    arr = render_skeleton(skel, height=20, width=20)
    assert arr.shape == (20, 20, 4)


# ---------------------------------------------------------------------------
# Dock smoke
# ---------------------------------------------------------------------------


def test_pose_dock_exposes_skeleton(qapp):
    from Imervue.paint.pose_dock import PoseDock
    dock = PoseDock()
    try:
        skel = dock.skeleton()
        assert isinstance(skel, PoseSkeleton)
        assert "head" in skel.joints
    finally:
        dock.deleteLater()


def test_pose_dock_insert_button_emits_skeleton(qapp):
    from Imervue.paint.pose_dock import PoseDock
    dock = PoseDock()
    try:
        emitted = []
        dock.insert_requested.connect(emitted.append)
        dock._on_insert()    # noqa: SLF001
        assert len(emitted) == 1
        assert isinstance(emitted[0], PoseSkeleton)
    finally:
        dock.deleteLater()


def test_pose_dock_reset_restores_default(qapp):
    from Imervue.paint.pose_dock import PoseDock
    dock = PoseDock()
    try:
        dock.skeleton().move_joint("head", 0.0, 0.0)
        assert dock.skeleton().joint("head").x == pytest.approx(0.0)
        dock._on_reset()    # noqa: SLF001
        assert dock.skeleton().joint("head").x == pytest.approx(0.50)
    finally:
        dock.deleteLater()
