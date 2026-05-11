"""Tests for the motion timeline editor.

Drives the widget under ``qapp`` without spawning a window — we
mutate via the public mutation methods (``update_endpoint`` /
``update_control``) so the test doesn't have to fake QGraphicsScene
events. The handle classes' ``itemChange`` glue is exercised
indirectly through these.
"""
from __future__ import annotations

import pytest

from puppet.document import Motion, MotionSegment, MotionTrack
from puppet.motion_timeline import MotionTimelineDialog, MotionTimelineWidget


def _two_segment_motion() -> Motion:
    return Motion(
        name="test",
        duration=1.0,
        tracks=[
            MotionTrack(
                param_id="ParamX",
                segments=[
                    MotionSegment(type="linear", p0=(0.0, 0.0), p1=(0.5, 0.5)),
                    MotionSegment(type="linear", p0=(0.5, 0.5), p1=(1.0, 1.0)),
                ],
            ),
        ],
    )


def _bezier_motion() -> Motion:
    return Motion(
        name="bez",
        duration=1.0,
        tracks=[
            MotionTrack(
                param_id="ParamY",
                segments=[
                    MotionSegment(
                        type="cubic-bezier",
                        p0=(0.0, 0.0), p1=(1.0, 1.0),
                        c0=(0.2, 0.0), c1=(0.8, 1.0),
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Widget setup
# ---------------------------------------------------------------------------


def test_widget_sets_no_track_initially(qapp):
    w = MotionTimelineWidget()
    try:
        assert w.motion() is None
        assert w.track() is None
    finally:
        w.deleteLater()


def test_set_track_binds_motion_and_track(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _two_segment_motion()
        w.set_track(motion, motion.tracks[0])
        assert w.motion() is motion
        assert w.track() is motion.tracks[0]
    finally:
        w.deleteLater()


def test_scene_to_track_round_trips_midpoint(qapp):
    """The coordinate mapping must be exact at the canvas midpoint —
    handle drags rely on it to write the right segment values."""
    w = MotionTimelineWidget()
    try:
        motion = _two_segment_motion()
        w.set_track(motion, motion.tracks[0])
        # Convert a known (t, v) point to scene coords and back.
        scene_point = w._scene_point(0.5, 0.0)   # noqa: SLF001
        t, v = w.scene_to_track(scene_point)
        assert t == pytest.approx(0.5, abs=1e-3)
        assert v == pytest.approx(0.0, abs=1e-3)
    finally:
        w.deleteLater()


# ---------------------------------------------------------------------------
# Endpoint dragging
# ---------------------------------------------------------------------------


def test_update_endpoint_moves_segment_p1(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _two_segment_motion()
        w.set_track(motion, motion.tracks[0])
        # Move segment 0's p1 to (t=0.7, v=0.3)
        new_point = w._scene_point(0.7, 0.3)   # noqa: SLF001
        w.update_endpoint(0, new_point)
        seg0 = motion.tracks[0].segments[0]
        seg1 = motion.tracks[0].segments[1]
        assert seg0.p1[0] == pytest.approx(0.7, abs=1e-3)
        assert seg0.p1[1] == pytest.approx(0.3, abs=1e-3)
        # The following segment's p0 must stay aligned to the previous p1.
        assert seg1.p0 == seg0.p1
    finally:
        w.deleteLater()


def test_update_endpoint_at_start_only_moves_p0_of_first_segment(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _two_segment_motion()
        w.set_track(motion, motion.tracks[0])
        new_point = w._scene_point(0.1, 0.2)   # noqa: SLF001
        w.update_endpoint(0, new_point, is_start=True)
        seg0 = motion.tracks[0].segments[0]
        assert seg0.p0[0] == pytest.approx(0.1, abs=1e-3)
        assert seg0.p0[1] == pytest.approx(0.2, abs=1e-3)
    finally:
        w.deleteLater()


def test_update_endpoint_emits_track_modified_signal(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _two_segment_motion()
        w.set_track(motion, motion.tracks[0])
        fired = []
        w.track_modified.connect(lambda: fired.append(True))
        w.update_endpoint(0, w._scene_point(0.6, 0.6))   # noqa: SLF001
        assert fired   # at least one emission
    finally:
        w.deleteLater()


# ---------------------------------------------------------------------------
# Bezier control handles
# ---------------------------------------------------------------------------


def test_update_control_moves_bezier_c0(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _bezier_motion()
        w.set_track(motion, motion.tracks[0])
        new_point = w._scene_point(0.3, -0.2)   # noqa: SLF001
        w.update_control(0, "c0", new_point)
        seg = motion.tracks[0].segments[0]
        assert seg.c0[0] == pytest.approx(0.3, abs=1e-3)
        assert seg.c0[1] == pytest.approx(-0.2, abs=1e-3)


    finally:
        w.deleteLater()


def test_update_control_moves_bezier_c1(qapp):
    w = MotionTimelineWidget()
    try:
        motion = _bezier_motion()
        w.set_track(motion, motion.tracks[0])
        new_point = w._scene_point(0.9, 0.7)   # noqa: SLF001
        w.update_control(0, "c1", new_point)
        seg = motion.tracks[0].segments[0]
        assert seg.c1[0] == pytest.approx(0.9, abs=1e-3)
        assert seg.c1[1] == pytest.approx(0.7, abs=1e-3)
    finally:
        w.deleteLater()


# ---------------------------------------------------------------------------
# Dialog wrapper
# ---------------------------------------------------------------------------


def test_dialog_picks_first_track_by_default(qapp):
    motion = _two_segment_motion()
    dlg = MotionTimelineDialog(motion)
    try:
        assert dlg.widget().track() is motion.tracks[0]
    finally:
        dlg.deleteLater()
