"""Tests for the motion recorder + bake_to_motion helper."""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import (
    Drawable,
    Parameter,
    PuppetDocument,
)
from puppet.motion_recorder import (
    MotionRecorder,
    append_motion,
    bake_to_motion,
)


def _doc_with_params() -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    doc.parameters = [
        Parameter(id="A", min=-1.0, max=1.0, default=0.0, keys=[]),
        Parameter(id="B", min=-1.0, max=1.0, default=0.0, keys=[]),
    ]
    return doc


# ---------------------------------------------------------------------------
# bake_to_motion
# ---------------------------------------------------------------------------


def test_bake_empty_samples_yields_zero_duration_motion():
    motion = bake_to_motion("idle", [])
    assert motion.name == "idle"
    assert motion.duration == pytest.approx(0.0)
    assert motion.tracks == []


def test_bake_drops_flat_parameter_tracks():
    samples = [
        (0.0, {"A": 0.0, "B": 0.0}),
        (0.5, {"A": 0.5, "B": 0.0}),
        (1.0, {"A": 1.0, "B": 0.0}),
    ]
    motion = bake_to_motion("wave", samples)
    track_ids = [t.param_id for t in motion.tracks]
    assert "A" in track_ids
    assert "B" not in track_ids   # flat → dropped


def test_bake_emits_linear_segments_between_samples():
    samples = [
        (0.0, {"A": 0.0}),
        (1.0, {"A": 1.0}),
        (2.0, {"A": 0.0}),
    ]
    motion = bake_to_motion("wave", samples)
    track = motion.tracks[0]
    assert len(track.segments) == 2
    assert track.segments[0].type == "linear"
    assert track.segments[0].p0 == (0.0, 0.0)
    assert track.segments[0].p1 == (1.0, 1.0)
    assert track.segments[1].p1 == (2.0, 0.0)


def test_bake_uses_relative_time_starting_from_zero():
    samples = [
        (10.0, {"A": 0.0}),
        (10.5, {"A": 1.0}),
    ]
    motion = bake_to_motion("late", samples)
    track = motion.tracks[0]
    assert track.segments[0].p0[0] == pytest.approx(0.0)
    assert track.segments[0].p1[0] == pytest.approx(0.5)
    assert motion.duration == pytest.approx(0.5)


def test_bake_preserves_loop_flag():
    samples = [(0.0, {"A": 0.0}), (1.0, {"A": 1.0})]
    assert bake_to_motion("a", samples, loop=False).loop is False
    assert bake_to_motion("a", samples, loop=True).loop is True


# ---------------------------------------------------------------------------
# MotionRecorder lifecycle
# ---------------------------------------------------------------------------


def test_recorder_starts_idle(qapp):
    canvas = PuppetCanvas()
    rec = MotionRecorder(canvas)
    try:
        assert rec.is_recording() is False
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_rejects_blank_name(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    try:
        assert rec.start("") is False
        assert rec.start("   ") is False
        assert rec.is_recording() is False
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_double_start_refused(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    try:
        assert rec.start("first") is True
        assert rec.start("second") is False
        rec.stop()
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_stop_returns_motion(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    try:
        rec.start("user_motion")
        canvas.set_parameter_value("A", 0.5)
        motion = rec.stop()
        assert motion is not None
        assert motion.name == "user_motion"
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_stop_when_idle_returns_none(qapp):
    canvas = PuppetCanvas()
    rec = MotionRecorder(canvas)
    try:
        assert rec.stop() is None
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_recorder_emits_finished_signal(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    captured: list = []
    rec.finished.connect(lambda m: captured.append(m))
    try:
        rec.start("anim")
        rec.stop()
        assert captured
        assert captured[-1].name == "anim"
    finally:
        rec.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# append_motion
# ---------------------------------------------------------------------------


def test_append_motion_adds_to_document(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    try:
        rec.start("custom")
        canvas.set_parameter_value("A", 0.5)
        motion = rec.stop()
        assert append_motion(canvas, motion) is True
        assert "custom" in [m.name for m in canvas.document().motions]
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_append_motion_replaces_existing_by_name(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_params())
    rec = MotionRecorder(canvas)
    try:
        rec.start("custom")
        rec.stop()
        # Append twice → second replaces first
        motion1 = bake_to_motion("custom", [(0.0, {"A": 0.0})])
        append_motion(canvas, motion1)
        motion2 = bake_to_motion("custom", [(0.0, {"A": 1.0})])
        append_motion(canvas, motion2)
        names = [m.name for m in canvas.document().motions]
        assert names.count("custom") == 1
    finally:
        rec.deleteLater()
        canvas.deleteLater()


def test_append_motion_no_document_returns_false(qapp):
    canvas = PuppetCanvas()
    motion = bake_to_motion("x", [(0.0, {"A": 0.0})])
    try:
        assert append_motion(canvas, motion) is False
    finally:
        canvas.deleteLater()
