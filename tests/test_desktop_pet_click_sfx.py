"""Tests for the click sound-effects player.

Pure helper :func:`coerce_paths_map` runs without Qt. The Qt
wrapper tests stub :class:`QSoundEffect` because the real one
requires audio hardware + a running event loop, neither of which
is available on headless CI.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet.click_sfx import (
    EVENT_CLICK,
    EVENT_DRAG,
    EVENT_DROP,
    EVENT_NOTIFY,
    SFX_EVENTS,
    ClickSfxPlayer,
    coerce_paths_map,
)


# ---------------------------------------------------------------
# coerce_paths_map
# ---------------------------------------------------------------


def test_coerce_paths_keeps_existing_files(tmp_path):
    """Real files on disk → kept verbatim."""
    wav = tmp_path / "click.wav"
    wav.write_bytes(b"RIFF")
    out = coerce_paths_map({EVENT_CLICK: str(wav)})
    assert out == {EVENT_CLICK: str(wav)}


def test_coerce_paths_drops_missing_files(tmp_path):
    """A path pointing nowhere → drop silently. Avoids a "user
    deleted the file" entry sitting in settings forever."""
    out = coerce_paths_map({EVENT_CLICK: str(tmp_path / "gone.wav")})
    assert out == {}


def test_coerce_paths_drops_unknown_events(tmp_path):
    """Forward-compat: a future-schema event name from another
    runtime version must be ignored, not propagated."""
    wav = tmp_path / "sound.wav"
    wav.write_bytes(b"RIFF")
    out = coerce_paths_map({
        EVENT_CLICK: str(wav),
        "future_event_v2": str(wav),
    })
    assert out == {EVENT_CLICK: str(wav)}


def test_coerce_paths_drops_non_string_values():
    """A misconfigured settings file mustn't crash the dispatcher."""
    out = coerce_paths_map({
        EVENT_CLICK: 42,
        EVENT_DRAG: None,
        EVENT_NOTIFY: "",
    })
    assert out == {}


def test_coerce_paths_handles_non_dict_input():
    assert coerce_paths_map(None) == {}
    assert coerce_paths_map([]) == {}
    assert coerce_paths_map("hi") == {}


def test_sfx_events_constant_covers_documented_set():
    """If a future change adds a fifth event, the workspace UI +
    every call site needs auditing — cross-check the canonical
    tuple here so the test fails loud and forces the audit."""
    assert SFX_EVENTS == (EVENT_CLICK, EVENT_DRAG, EVENT_DROP, EVENT_NOTIFY)


# ---------------------------------------------------------------
# ClickSfxPlayer
# ---------------------------------------------------------------


class _StubEffect:
    """Records every interaction so tests can assert on play /
    volume / source without spinning up audio hardware."""

    def __init__(self, _parent=None) -> None:
        self.source = None
        self.volume = None
        self.play_calls = 0
        self.stop_calls = 0

    def setSource(self, url) -> None:   # noqa: N802  # NOSONAR  # mirrors QSoundEffect.setSource so duck-typing works
        self.source = url

    def setVolume(self, value) -> None:   # noqa: N802  # NOSONAR  # mirrors QSoundEffect.setVolume so duck-typing works
        self.volume = value

    def play(self) -> None:
        self.play_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


@pytest.fixture
def stub_qsoundeffect(monkeypatch):
    """Replace ``QSoundEffect`` constructor for the duration of
    one test. The player imports it lazily inside
    ``_ensure_effect``, so we patch the attribute on the lazy
    import path."""
    from PySide6 import QtMultimedia
    monkeypatch.setattr(QtMultimedia, "QSoundEffect", _StubEffect)
    yield


def test_player_starts_silent(qapp):
    """Fresh player with no paths configured → no effects, no
    play calls. The lazy import doesn't run either."""
    player = ClickSfxPlayer()
    try:
        assert player.paths() == {}
        assert player.play(EVENT_CLICK) is False
    finally:
        player.deleteLater()


def test_play_returns_false_for_unknown_event(qapp, tmp_path, stub_qsoundeffect):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        assert player.play("nonsense_event") is False
    finally:
        player.deleteLater()


def test_play_uses_configured_path(qapp, tmp_path, stub_qsoundeffect):
    wav = tmp_path / "click.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        assert player.play(EVENT_CLICK) is True
        effect = player._effects[EVENT_CLICK]   # noqa: SLF001
        assert effect.play_calls == 1
        # Subsequent plays reuse the same effect (low-latency replay).
        player.play(EVENT_CLICK)
        assert effect.play_calls == 2
    finally:
        player.deleteLater()


def test_set_paths_drops_effect_for_removed_event(
    qapp, tmp_path, stub_qsoundeffect,
):
    """Removing an event's path mid-session must tear down the
    cached effect — otherwise the deleted source URL would still
    fire on the next play."""
    wav = tmp_path / "click.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        player.play(EVENT_CLICK)
        assert EVENT_CLICK in player._effects   # noqa: SLF001
        player.set_paths({})
        assert EVENT_CLICK not in player._effects   # noqa: SLF001
        assert player.play(EVENT_CLICK) is False
    finally:
        player.deleteLater()


def test_set_volume_clamps_and_propagates(qapp, tmp_path, stub_qsoundeffect):
    """Volume out of range clamps to [0, 1]; live effects pick up
    the new value so a slider drag is audible immediately."""
    wav = tmp_path / "click.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        player.play(EVENT_CLICK)   # forces effect creation
        player.set_volume(2.5)
        assert player.volume() == 1.0   # NOSONAR  # exact representable value asserted intentionally
        assert player._effects[EVENT_CLICK].volume == 1.0   # noqa: SLF001   # NOSONAR  # exact representable value asserted intentionally
        player.set_volume(-0.5)
        assert player.volume() == 0.0   # NOSONAR  # exact representable value asserted intentionally
        assert player._effects[EVENT_CLICK].volume == 0.0   # noqa: SLF001   # NOSONAR  # exact representable value asserted intentionally
    finally:
        player.deleteLater()


def test_play_without_path_for_event_is_silent(
    qapp, tmp_path, stub_qsoundeffect,
):
    """Configure click only → drag / drop / notify stay silent.
    Per-event opt-in is the whole point of the paths map."""
    wav = tmp_path / "click.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        assert player.play(EVENT_CLICK) is True
        assert player.play(EVENT_DRAG) is False
        assert player.play(EVENT_DROP) is False
        assert player.play(EVENT_NOTIFY) is False
    finally:
        player.deleteLater()


def test_shutdown_stops_every_effect(qapp, tmp_path, stub_qsoundeffect):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    player = ClickSfxPlayer()
    try:
        player.set_paths({
            EVENT_CLICK: str(wav),
            EVENT_DROP: str(wav),
        })
        player.play(EVENT_CLICK)
        player.play(EVENT_DROP)
        player.shutdown()
        # Internally we don't expose individual stop counts after
        # shutdown clears the cache, so verify the cache is empty.
        assert player._effects == {}   # noqa: SLF001
    finally:
        player.deleteLater()


def test_play_handles_missing_qtmultimedia(qapp, tmp_path, monkeypatch):
    """If QtMultimedia somehow isn't importable (stripped PySide6),
    ``play`` returns False gracefully instead of raising."""
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    import sys

    monkeypatch.setitem(sys.modules, "PySide6.QtMultimedia", None)
    player = ClickSfxPlayer()
    try:
        player.set_paths({EVENT_CLICK: str(wav)})
        assert player.play(EVENT_CLICK) is False
    finally:
        player.deleteLater()
