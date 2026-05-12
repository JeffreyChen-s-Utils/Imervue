"""Tests for the Idle motion cycler.

The cycler's QTimer runs in real time, which makes wall-clock tests
flaky. We exercise it via the public methods directly
(``set_enabled``, ``pick_next``) and the internal tick
(``_on_tick``) so the watchdog logic is deterministic.
"""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import (
    Drawable,
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from puppet.idle_motion_cycler import IdleMotionCycler
from puppet.motion_player import MotionPlayer


def _motion(name: str, group: str | None) -> Motion:
    return Motion(
        name=name, duration=1.0, loop=False, group=group,
        tracks=[MotionTrack(
            param_id="ParamX",
            segments=[MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 1.0))],
        )],
    )


def _doc_with(*motions: Motion) -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [Parameter(id="ParamX", min=-1.0, max=1.0, default=0.0)]
    doc.motions = list(motions)
    return doc


# ---------------------------------------------------------------------------
# Enable / disable plumbing
# ---------------------------------------------------------------------------


def test_cycler_starts_disabled(qapp):
    canvas = PuppetCanvas()
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        assert cycler.is_enabled() is False
    finally:
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_enable_emits_state_changed(qapp):
    canvas = PuppetCanvas()
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    fired: list[int] = []
    cycler.state_changed.connect(lambda: fired.append(1))
    try:
        cycler.set_enabled(True)
        cycler.set_enabled(True)   # idempotent
        cycler.set_enabled(False)
        assert fired == [1, 1]
    finally:
        cycler.set_enabled(False)
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_set_cycle_duration_clamps_to_min(qapp):
    canvas = PuppetCanvas()
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        cycler.set_cycle_duration(0.01)
        assert cycler.cycle_duration() >= 0.5
        cycler.set_cycle_duration(15.0)
        assert cycler.cycle_duration() == pytest.approx(15.0)
    finally:
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# pick_next behaviour
# ---------------------------------------------------------------------------


def test_pick_next_with_no_idle_motions_returns_none(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("tap", "TapHead")))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        assert cycler.pick_next() is None
        assert player.motion() is None
    finally:
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_pick_next_single_idle_picks_that_one(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("only_idle", "Idle")))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        picked = cycler.pick_next()
        assert picked is not None
        assert picked.name == "only_idle"
        assert player.is_playing() is True
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_pick_next_avoids_replay_when_alternatives_exist(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(
        _motion("idle_a", "Idle"),
        _motion("idle_b", "Idle"),
    ))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        first = cycler.pick_next()
        second = cycler.pick_next()
        third = cycler.pick_next()
        # With only two candidates, after picking one the other is the
        # only option — back-to-back replay must not occur.
        assert first.name != second.name
        assert second.name != third.name
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_pick_next_with_single_idle_replays_it(qapp):
    """When the document carries exactly one Idle, the cycler keeps
    rebinding the same motion rather than going silent."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("only", "Idle")))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        first = cycler.pick_next()
        second = cycler.pick_next()
        assert first.name == second.name == "only"
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Yield logic — don't interrupt non-Idle playback
# ---------------------------------------------------------------------------


def test_tick_yields_when_non_idle_motion_is_playing(qapp):
    """When a HitArea triggers (say) a TapHead motion, the cycler
    must not steal control mid-playback. We bind the non-Idle motion
    manually, then drive the tick — the cycler should leave the
    player alone."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(
        _motion("idle_a", "Idle"),
        _motion("tap", "TapHead"),
    ))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        tap = canvas.document().motions[1]
        player.set_motion(tap)
        player.play()
        cycler.set_enabled(True)
        cycler._on_tick()   # noqa: SLF001 — direct dispatch for determinism
        # Player still bound to tap, not swapped to idle_a
        assert player.motion().name == "tap"
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_tick_picks_idle_when_player_is_idle(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("idle_a", "Idle")))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        cycler.set_enabled(True)
        cycler._on_tick()   # noqa: SLF001
        assert player.motion() is not None
        assert player.motion().group == "Idle"
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_tick_is_a_noop_when_disabled(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(_motion("idle_a", "Idle")))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        cycler._on_tick()   # noqa: SLF001 — disabled, nothing should happen
        assert player.motion() is None
    finally:
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


def test_tick_no_document_is_safe(qapp):
    canvas = PuppetCanvas()
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        cycler.set_enabled(True)
        cycler._on_tick()   # noqa: SLF001 — no document loaded, must not raise
        assert player.motion() is None
    finally:
        cycler.set_enabled(False)
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Configurable group
# ---------------------------------------------------------------------------


def test_set_group_changes_the_picked_group(qapp):
    """The default group is 'Idle' but the cycler can target any
    custom group — handy for rigs that name their idle clips something
    else (e.g. 'Wait')."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with(
        _motion("idle_a", "Idle"),
        _motion("wait_a", "Wait"),
    ))
    player = MotionPlayer(canvas)
    cycler = IdleMotionCycler(player, canvas)
    try:
        cycler.set_group("Wait")
        picked = cycler.pick_next()
        assert picked is not None
        assert picked.name == "wait_a"
    finally:
        cycler.set_enabled(False)
        player.stop()
        cycler.deleteLater()
        player.deleteLater()
        canvas.deleteLater()
