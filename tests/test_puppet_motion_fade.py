"""Tests for the motion fade-in / fade-out / crossfade behaviour added
to :class:`MotionPlayer`.

We construct the player by hand against a real ``PuppetCanvas`` so the
parameter-write path is exercised end-to-end. Time is driven via
``player.step(dt)`` (seeks the playhead) rather than the wall clock so
the tests stay deterministic.
"""
from __future__ import annotations

import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from Imervue.puppet.motion_player import MotionPlayer


def _two_motion_doc() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    doc.parameters = [
        Parameter(id="ParamX", min=-1.0, max=1.0, default=0.0, keys=[]),
    ]
    # Two motions on the same parameter — first goes 0 → 1 linearly,
    # second jumps to 0.5 (constant) so the fade math is obvious.
    motion_one = Motion(
        name="ramp",
        duration=1.0,
        tracks=[
            MotionTrack(
                param_id="ParamX",
                segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
            ),
        ],
    )
    motion_two = Motion(
        name="hold",
        duration=1.0,
        fade_in_duration=0.5,
        fade_out_duration=0.4,
        tracks=[
            MotionTrack(
                param_id="ParamX",
                segments=[MotionSegment(type="linear", p0=(0.0, 0.5), p1=(1.0, 0.5))],
            ),
        ],
    )
    doc.motions = [motion_one, motion_two]
    return doc


# ---------------------------------------------------------------------------
# Fade-in
# ---------------------------------------------------------------------------


def test_first_bind_has_no_fade_in_state(qapp):
    """No previous motion means no fade source — the first ``set_motion``
    on a fresh player must be snap-bind to preserve legacy behaviour."""
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    try:
        ramp = canvas.document().motions[0]
        player.set_motion(ramp)
        player.seek(0.5)
        # No fade — direct sample: linear 0..1 at t=0.5 → 0.5
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.5, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_crossfade_lerps_from_previous_value(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    try:
        ramp, hold = canvas.document().motions
        # Bind first motion so the next bind has a "previous motion".
        # Then explicitly set the canvas value — we don't rely on
        # seek(duration) because the default loop=True wraps to t=0.
        player.set_motion(ramp)
        canvas.set_parameter_value("ParamX", 1.0)
        # Bind hold. fade_in_duration=0.5, target value 0.5.
        player.set_motion(hold)
        player.seek(0.25)
        # progress = 0.25 / 0.5 = 0.5 → lerp(1.0, 0.5, 0.5) = 0.75
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.75, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_after_fade_window_uses_sampled_directly(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    try:
        ramp, hold = canvas.document().motions
        player.set_motion(ramp)
        canvas.set_parameter_value("ParamX", 1.0)
        player.set_motion(hold)
        player.seek(0.9)
        # Past the 0.5s fade window — must be exactly the sampled value
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.5, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_default_fade_in_kicks_in_for_motion_without_field(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    player.set_default_fade(0.5, 0.5)
    try:
        ramp, _ = canvas.document().motions
        # Bind ramp first so the next bind has a "previous motion"
        player.set_motion(ramp)
        canvas.set_parameter_value("ParamX", 0.8)
        # Rebind ramp itself — it has fade_in=0 so the default kicks in.
        player.set_motion(ramp)
        player.seek(0.25)
        # ramp at t=0.25 = 0.25; lerp(0.8, 0.25, 0.5) = 0.525
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.525, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Fade-out
# ---------------------------------------------------------------------------


def test_stop_without_fade_falls_back_to_snap(qapp):
    """A motion with no fade_out and no default fade should ``stop()``
    by snapping back to motion-at-t=0 — the legacy behaviour."""
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    try:
        ramp = canvas.document().motions[0]
        player.set_motion(ramp)
        player.seek(0.5)
        player.stop()
        assert player.is_playing() is False
        assert player.is_fading_out() is False
        # Ramp at t=0 == 0
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.0, abs=1e-3)
    finally:
        player.deleteLater()
        canvas.deleteLater()


def test_stop_with_fade_out_enters_fading_state(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_two_motion_doc())
    player = MotionPlayer(canvas)
    try:
        _, hold = canvas.document().motions
        # First-bind suppresses fade-in; bind hold and step past its window
        player.set_motion(hold)
        player.seek(0.9)
        assert canvas.parameter_values()["ParamX"] == pytest.approx(0.5, abs=1e-3)
        player.stop()
        # hold.fade_out_duration > 0 → player should now be fading out,
        # not in the snap-stop state.
        assert player.is_fading_out() is True
        assert player.is_playing() is False
    finally:
        player.deleteLater()
        canvas.deleteLater()
