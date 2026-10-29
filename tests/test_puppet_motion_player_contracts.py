"""Contracts for :class:`MotionPlayer` that hold whichever module owns each step.

Pins the values the player writes over time (a grid of seeks across looping
and one-shot motions, the fade-in blend, the fade-out ease), the tick / stop /
pause transitions, the group pick, the ``state_changed`` emissions and the
sound hooks. A stand-in canvas records every batch the player writes (the real
one is a ``QOpenGLWidget``) and a fake clock replaces ``time.monotonic`` so the
timer-driven paths run deterministically.
"""
from __future__ import annotations

import logging
import secrets
import sys
import time

import pytest
from PySide6.QtCore import QObject

from Imervue.puppet.document import (
    Motion,
    MotionSegment,
    MotionTrack,
    Parameter,
    PuppetDocument,
)
from Imervue.puppet.motion_player import MotionPlayer


class _Canvas(QObject):
    """Records every batch the player writes."""

    def __init__(self, document=None, values=None):
        super().__init__()
        self._document = document
        self.values: dict[str, float] = dict(values or {})
        self.writes: list[dict[str, float]] = []

    def document(self):
        return self._document

    def parameter_values(self):
        return dict(self.values)

    def set_parameter_values(self, values):
        self.writes.append(dict(values))
        self.values.update(values)


class _Clock:
    def __init__(self, now: float = 100.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class _Effect:
    def __init__(self, fail_stop: bool = False):
        self.calls: list[tuple] = []
        self._fail_stop = fail_stop

    def setSource(self, url):  # noqa: N802 - mirrors QSoundEffect
        self.calls.append(("source", url.toLocalFile()))

    def play(self):
        self.calls.append(("play",))

    def stop(self):
        self.calls.append(("stop",))
        if self._fail_stop:
            raise RuntimeError("already deleted")


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


def _motion(*, loop=True, fade_in=0.0, fade_out=0.0, name="a", group=None,
            sound=None) -> Motion:
    x = MotionTrack("x", [
        MotionSegment("linear", (0.0, 0.0), (1.0, 4.0)),
        MotionSegment("cubic-bezier", (1.0, 4.0), (2.0, 0.0),
                      c0=(1.3, 4.0), c1=(1.7, 0.0)),
    ])
    y = MotionTrack("y", [
        MotionSegment("stepped", (0.0, 1.0), (1.0, 3.0)),
        MotionSegment("inverse-stepped", (1.0, 3.0), (2.0, 5.0)),
    ])
    w = MotionTrack("w", [MotionSegment("linear", (0.0, 2.0), (2.0, 6.0))])
    return Motion(name=name, duration=2.0, loop=loop, tracks=[x, y, w],
                  fade_in_duration=fade_in, fade_out_duration=fade_out,
                  group=group, sound_path=sound)


def _doc() -> PuppetDocument:
    doc = PuppetDocument(size=(8, 8))
    doc.parameters = [Parameter("x", -10.0, 10.0, 1.0),
                      Parameter("y", -10.0, 10.0, -1.0)]
    return doc


def _player(canvas) -> tuple[MotionPlayer, list[int]]:
    player = MotionPlayer(canvas)
    emits: list[int] = []
    player.state_changed.connect(lambda: emits.append(1))
    return player, emits


def _grid_trace(*, loop: bool):
    canvas = _Canvas()
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion(loop=loop))
        rows = []
        for i in range(-1, 19):
            player.seek(i * 0.25)
            rows.append((player.elapsed(), canvas.writes[-1]))
        return rows
    finally:
        player.deleteLater()


def _fade_in_trace():
    canvas = _Canvas(values={"x": 10.0, "y": -2.0, "z": 7.0})
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion(name="prev"))
        player.set_motion(_motion(fade_in=1.0))
        rows = []
        for t in (0.0, 0.25, 0.5, 0.75, 0.999, 1.0, 1.5, 0.5):
            player.seek(t)
            rows.append(canvas.writes[-1])
        return rows
    finally:
        player.deleteLater()


_LOOP_GRID = [
    (0.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (0.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (0.25, {'x': 1.0, 'y': 1.0, 'w': 2.5}),
    (0.5, {'x': 2.0, 'y': 1.0, 'w': 3.0}),
    (0.75, {'x': 3.0, 'y': 1.0, 'w': 3.5}),
    (1.0, {'x': 4.0, 'y': 1.0, 'w': 4.0}),
    (1.25, {'x': 3.3328829429446247, 'y': 5.0, 'w': 4.5}),
    (1.5, {'x': 2.0, 'y': 5.0, 'w': 5.0}),
    (1.75, {'x': 0.6671170570553766, 'y': 5.0, 'w': 5.5}),
    (2.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (2.25, {'x': 1.0, 'y': 1.0, 'w': 2.5}),
    (2.5, {'x': 2.0, 'y': 1.0, 'w': 3.0}),
    (2.75, {'x': 3.0, 'y': 1.0, 'w': 3.5}),
    (3.0, {'x': 4.0, 'y': 1.0, 'w': 4.0}),
    (3.25, {'x': 3.3328829429446247, 'y': 5.0, 'w': 4.5}),
    (3.5, {'x': 2.0, 'y': 5.0, 'w': 5.0}),
    (3.75, {'x': 0.6671170570553766, 'y': 5.0, 'w': 5.5}),
    (4.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (4.25, {'x': 1.0, 'y': 1.0, 'w': 2.5}),
    (4.5, {'x': 2.0, 'y': 1.0, 'w': 3.0}),
]
_ONCE_GRID = [
    (0.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (0.0, {'x': 0.0, 'y': 1.0, 'w': 2.0}),
    (0.25, {'x': 1.0, 'y': 1.0, 'w': 2.5}),
    (0.5, {'x': 2.0, 'y': 1.0, 'w': 3.0}),
    (0.75, {'x': 3.0, 'y': 1.0, 'w': 3.5}),
    (1.0, {'x': 4.0, 'y': 1.0, 'w': 4.0}),
    (1.25, {'x': 3.3328829429446247, 'y': 5.0, 'w': 4.5}),
    (1.5, {'x': 2.0, 'y': 5.0, 'w': 5.0}),
    (1.75, {'x': 0.6671170570553766, 'y': 5.0, 'w': 5.5}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
    (2.0, {'x': 0.0, 'y': 5.0, 'w': 6.0}),
]
_FADE_IN_GRID = [
    {'x': 10.0, 'y': -2.0, 'w': 2.0},
    {'x': 7.75, 'y': -1.25, 'w': 2.5},
    {'x': 6.0, 'y': -0.5, 'w': 3.0},
    {'x': 4.75, 'y': 0.25, 'w': 3.5},
    {'x': 4.002004, 'y': 0.9969999999999999, 'w': 3.998},
    {'x': 4.0, 'y': 1.0, 'w': 4.0},
    {'x': 2.0, 'y': 5.0, 'w': 5.0},
    {'x': 2.0, 'y': 1.0, 'w': 3.0},
]


# ---- sampling grid -----------------------------------------------------


@pytest.mark.parametrize(("loop", "expected"), [
    (True, "_LOOP_GRID"), (False, "_ONCE_GRID"),
])
def test_seek_grid_writes_the_sampled_values(qapp, loop, expected):
    assert _grid_trace(loop=loop) == globals()[expected]


def test_fade_in_blends_from_the_previous_values_then_clears(qapp):
    assert _fade_in_trace() == _FADE_IN_GRID


def test_step_advances_from_the_current_playhead(qapp):
    canvas = _Canvas()
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion())
        player.step(0.5)
        player.step(0.25)
        assert player.elapsed() == 0.75
        assert canvas.writes[-1]["x"] == 3.0
    finally:
        player.deleteLater()


def test_seek_without_motion_writes_nothing_but_emits(qapp):
    canvas = _Canvas()
    player, emits = _player(canvas)
    try:
        player.seek(-3.0)
        assert player.elapsed() == 0.0
        player.seek(5.0)
        assert player.elapsed() == 5.0         # no motion: no clamp
        assert canvas.writes == []
        assert emits == [1, 1]
        assert player.duration() == 0.0
    finally:
        player.deleteLater()


# ---- binding ------------------------------------------------------------


def test_first_bind_never_fades_even_with_a_default(qapp):
    canvas = _Canvas(values={"x": 9.0})
    player = MotionPlayer(canvas)
    try:
        player.set_default_fade(1.0, 1.0)
        player.set_motion(_motion())
        player.seek(0.5)
        assert canvas.writes[-1] == {"x": 2.0, "y": 1.0, "w": 3.0}
    finally:
        player.deleteLater()


def test_default_fade_in_applies_when_the_motion_has_none(qapp):
    canvas = _Canvas(values={"x": 8.0})
    player = MotionPlayer(canvas)
    try:
        player.set_default_fade(2.0, 0.0)
        player.set_motion(_motion(name="prev"))
        player.set_motion(_motion())
        player.seek(1.0)
        assert canvas.writes[-1] == {"x": 6.0, "y": 1.0, "w": 4.0}
    finally:
        player.deleteLater()


def test_rebinding_with_zero_fade_snaps(qapp):
    canvas = _Canvas(values={"x": 8.0})
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion(name="prev"))
        player.set_motion(_motion())
        player.seek(0.5)
        assert canvas.writes[-1] == {"x": 2.0, "y": 1.0, "w": 3.0}
    finally:
        player.deleteLater()


def test_set_motion_stops_playback_and_resets_time(qapp, clock):
    canvas = _Canvas()
    player, emits = _player(canvas)
    try:
        player.set_motion(_motion())
        player.play()
        player.seek(1.0)
        player.set_motion(_motion(loop=False))
        assert (player.is_playing(), player.elapsed(), player.loop()) == (
            False, 0.0, False)
        assert not player._timer.isActive()  # noqa: SLF001
        player.set_motion(None)
        assert player.motion() is None
        assert player.loop() is False
        assert emits == [1, 1, 1, 1, 1]
    finally:
        player.deleteLater()


def test_set_default_fade_clamps_negatives(qapp):
    player = MotionPlayer(_Canvas())
    try:
        player.set_default_fade(-1.0, "0.5")
        assert (player.default_fade_in(), player.default_fade_out()) == (0.0, 0.5)
    finally:
        player.deleteLater()


# ---- transport ------------------------------------------------------------


def test_play_requires_a_motion_and_is_idempotent(qapp, clock):
    player, emits = _player(_Canvas())
    try:
        player.play()
        assert emits == []
        player.set_motion(_motion())
        player.seek(0.5)
        clock.now = 50.0
        player.play()
        player.play()
        assert player.is_playing() is True
        assert player._wall_anchor == 49.5  # noqa: SLF001
        assert emits == [1, 1, 1]
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_seek_while_playing_reanchors_the_wall_clock(qapp, clock):
    player = MotionPlayer(_Canvas())
    try:
        player.set_motion(_motion())
        player.play()
        clock.now = 200.0
        player.seek(1.25)
        assert player._wall_anchor == 198.75  # noqa: SLF001
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_tick_follows_the_clock_and_wraps_a_loop(qapp, clock):
    canvas = _Canvas()
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion())
        player.play()
        clock.now += 2.5
        player._on_tick()  # noqa: SLF001
        assert player.elapsed() == 2.5
        assert canvas.writes[-1] == {"x": 2.0, "y": 1.0, "w": 3.0}
        assert player.is_playing() is True
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_tick_past_the_end_of_a_one_shot_clamps_and_pauses(qapp, clock):
    canvas = _Canvas()
    player, emits = _player(canvas)
    try:
        player.set_motion(_motion(loop=False))
        player.play()
        clock.now += 3.0
        player._on_tick()  # noqa: SLF001
        assert player.elapsed() == 2.0
        assert canvas.writes[-1] == {"x": 0.0, "y": 5.0, "w": 6.0}
        assert player.is_playing() is False
        assert emits == [1, 1, 1]
    finally:
        player.deleteLater()


def test_tick_without_a_motion_pauses(qapp, clock):
    player, emits = _player(_Canvas())
    try:
        player._is_playing = True  # noqa: SLF001
        player._on_tick()  # noqa: SLF001
        assert player.is_playing() is False
        assert emits == [1]
    finally:
        player.deleteLater()


def test_pause_only_acts_while_playing_and_stops_sound(qapp, clock):
    player, emits = _player(_Canvas())
    effect = _Effect()
    try:
        player.pause()
        assert emits == []
        player.set_motion(_motion())
        player._sound_effect = effect  # noqa: SLF001
        player.play()
        player.pause()
        assert player.is_playing() is False
        assert effect.calls == [("stop",)]
        assert emits == [1, 1, 1]
    finally:
        player.deleteLater()


# ---- stop / fade-out ----------------------------------------------------------


def test_stop_when_idle_at_zero_does_nothing(qapp):
    player, emits = _player(_Canvas())
    try:
        player.set_motion(_motion(fade_out=1.0))
        player.stop()
        assert emits == [1]
    finally:
        player.deleteLater()


def test_stop_without_fade_snaps_to_frame_zero(qapp, clock):
    canvas = _Canvas()
    player, emits = _player(canvas)
    try:
        player.set_motion(_motion())
        player.seek(1.5)
        player.stop()
        assert player.elapsed() == 0.0
        assert canvas.writes[-1] == {"x": 0.0, "y": 1.0, "w": 2.0}
        assert emits == [1, 1, 1]
    finally:
        player.deleteLater()


def test_stop_with_fade_but_no_tracks_snaps(qapp, clock):
    canvas = _Canvas()
    player = MotionPlayer(canvas)
    try:
        player.set_motion(Motion(name="e", duration=1.0, fade_out_duration=1.0))
        player.seek(0.5)
        player.stop()
        assert player.is_fading_out() is False
        assert canvas.writes[-1] == {}
    finally:
        player.deleteLater()


def test_fade_out_eases_toward_defaults_then_snap_stops(qapp, clock):
    canvas = _Canvas(_doc(), values={"z": 9.0})
    player, emits = _player(canvas)
    try:
        player.set_motion(_motion(fade_out=2.0))
        player.play()
        player.seek(0.5)               # x=2, y=1, w=3 (+ z=9 kept)
        player.stop()
        assert player.is_fading_out() is True
        assert player.is_playing() is False
        assert player._timer.isActive()  # noqa: SLF001
        n = len(canvas.writes)
        clock.now += 1.0
        player._on_tick()  # noqa: SLF001
        assert canvas.writes[-1] == {"x": 1.5, "y": 0.0, "w": 3.0, "z": 9.0}
        assert player.is_fading_out() is True
        clock.now += 1.5
        player._on_tick()  # noqa: SLF001
        assert canvas.writes[-1] == {"x": 1.0, "y": -1.0, "w": 3.0, "z": 9.0}
        assert len(canvas.writes) == n + 2      # no frame-0 write after a fade
        assert player.is_fading_out() is False
        assert player.elapsed() == 0.0
        assert not player._timer.isActive()  # noqa: SLF001
        assert emits == [1, 1, 1, 1, 1]
    finally:
        player.deleteLater()


def test_stop_during_fade_out_snaps_immediately(qapp, clock):
    canvas = _Canvas(_doc())
    player = MotionPlayer(canvas)
    try:
        player.set_default_fade(0.0, 1.0)
        player.set_motion(_motion())
        player.seek(0.5)
        player.stop()
        n = len(canvas.writes)
        player.stop()
        assert player.is_fading_out() is False
        assert len(canvas.writes) == n
    finally:
        player.deleteLater()


def test_fade_out_without_document_targets_nothing(qapp, clock):
    canvas = _Canvas(None)
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion(fade_out=1.0))
        player.seek(0.5)
        player.stop()
        clock.now += 0.5
        player._on_tick()  # noqa: SLF001
        assert canvas.writes[-1] == {"x": 2.0, "y": 1.0, "w": 3.0}
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_fade_out_with_zero_total_completes_at_once(qapp, clock):
    canvas = _Canvas(_doc())
    player = MotionPlayer(canvas)
    try:
        player.set_motion(_motion(fade_out=1.0))
        player.seek(0.5)
        player.stop()
        player._fade_out_total = 0.0  # noqa: SLF001
        player._on_tick()  # noqa: SLF001
        assert canvas.writes[-1] == {"x": 1.0, "y": -1.0, "w": 3.0}
        assert player.is_fading_out() is False
    finally:
        player.deleteLater()


def test_start_fade_out_without_motion_is_a_no_op(qapp):
    player, emits = _player(_Canvas())
    try:
        player._start_fade_out()  # noqa: SLF001
        assert player.is_fading_out() is False
        assert emits == []
    finally:
        player.deleteLater()


# ---- groups ----------------------------------------------------------------


def test_play_group_without_candidates_returns_none(qapp):
    player = MotionPlayer(_Canvas())
    try:
        assert player.play_group("Tap", [_motion(group="Idle")]) is None
        assert player.motion() is None
    finally:
        player.deleteLater()


def test_play_group_single_candidate_skips_the_random_pick(qapp, clock,
                                                           monkeypatch):
    def _boom(_seq):
        raise AssertionError("choice called")
    monkeypatch.setattr(secrets, "choice", _boom)
    player = MotionPlayer(_Canvas())
    only = _motion(group="Tap")
    try:
        assert player.play_group("Tap", [_motion(group="Idle"), only]) is only
        assert player.motion() is only and player.is_playing()
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_play_group_picks_among_matching_candidates(qapp, clock, monkeypatch):
    seen = []

    def _last(seq):
        seen.append(list(seq))
        return seq[-1]
    monkeypatch.setattr(secrets, "choice", _last)
    a, b, c = (_motion(group="Idle", name=n) for n in "abc")
    player = MotionPlayer(_Canvas())
    try:
        assert player.play_group("Idle", [a, _motion(group="Tap"), b, c]) is c
        assert seen == [[a, b, c]]
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


# ---- sound ------------------------------------------------------------------


def test_play_starts_the_motion_sound(qapp, clock, tmp_path):
    wav = tmp_path / "s.wav"
    wav.write_bytes(b"RIFF")
    player = MotionPlayer(_Canvas())
    effect = _Effect()
    try:
        player._sound_effect = effect  # noqa: SLF001
        player.set_motion(_motion(sound=str(wav)))
        player.play()
        assert effect.calls == [("source", str(wav).replace("\\", "/")), ("play",)]
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_missing_sound_file_is_logged_and_skipped(qapp, clock, tmp_path, caplog):
    player = MotionPlayer(_Canvas())
    effect = _Effect()
    try:
        player._sound_effect = effect  # noqa: SLF001
        player.set_motion(_motion(sound=str(tmp_path / "none.wav")))
        with caplog.at_level(logging.DEBUG, logger="Imervue.plugin.puppet.motion_player"):
            player.play()
        assert effect.calls == []
        assert "missing on disk" in caplog.text
    finally:
        player._timer.stop()  # noqa: SLF001
        player.deleteLater()


def test_stop_sound_logs_a_runtime_error(qapp, caplog):
    player = MotionPlayer(_Canvas())
    try:
        player._sound_effect = _Effect(fail_stop=True)  # noqa: SLF001
        with caplog.at_level(logging.DEBUG, logger="Imervue.plugin.puppet.motion_player"):
            player._stop_sound()  # noqa: SLF001
        assert "sound stop failed: already deleted" in caplog.text
    finally:
        player.deleteLater()


def test_missing_qtmultimedia_disables_audio(qapp, monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "PySide6.QtMultimedia", None)
    player = MotionPlayer(_Canvas())
    try:
        with caplog.at_level(logging.INFO, logger="Imervue.plugin.puppet.motion_player"):
            assert player._ensure_sound_effect() is None  # noqa: SLF001
        assert "motion audio disabled" in caplog.text
    finally:
        player.deleteLater()


def test_existing_sound_effect_is_reused(qapp):
    player = MotionPlayer(_Canvas())
    effect = _Effect()
    try:
        player._sound_effect = effect  # noqa: SLF001
        assert player._ensure_sound_effect() is effect  # noqa: SLF001
    finally:
        player.deleteLater()
