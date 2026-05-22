"""Tests for the music-rhythm driver.

Pure-helper tests need only numpy; the Qt wrapper tests use the
``push_envelope`` / ``tick_once`` test hooks so no real audio
stream is opened (WASAPI loopback would need a running playback,
not portable across test environments).
"""
from __future__ import annotations

import math

import pytest

from Imervue.desktop_pet.music_rhythm import (
    DEFAULT_SMOOTHING_S,
    DEFAULT_SWAY_AMPLITUDE,
    DEFAULT_SWAY_PERIOD_S,
    MusicRhythmDriver,
    compute_envelope,
    envelope_to_sway,
    smooth_envelope,
)
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument
from Imervue.puppet.standard_params import (
    PARAM_ANGLE_Z,
    PARAM_BODY_ANGLE_Z,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------
# compute_envelope
# ---------------------------------------------------------------


def test_envelope_silence_is_zero():
    assert compute_envelope([[0.0], [0.0], [0.0]]) == 0.0   # NOSONAR  # exact representable value asserted intentionally


def test_envelope_unit_signal_is_one():
    """A constant ±1.0 signal has RMS exactly 1.0 — sanity check
    the normalisation."""
    block = [[1.0], [-1.0], [1.0], [-1.0]]
    assert compute_envelope(block) == pytest.approx(1.0)


def test_envelope_clips_above_one():
    """Some drivers report >1.0 samples (cooked loudness, etc.);
    the helper must clip rather than push >1.0 down the pipeline
    where it'd flip the rig past its parameter range."""
    block = [[2.0], [2.0], [2.0], [2.0]]
    assert compute_envelope(block) == 1.0   # NOSONAR  # exact representable value asserted intentionally


def test_envelope_empty_array_is_zero():
    assert compute_envelope([]) == 0.0   # NOSONAR  # exact representable value asserted intentionally


def test_envelope_handles_nan():
    """Audio drivers occasionally emit NaN on dropped buffers.
    Must not propagate into the rig."""
    block = [[float("nan")], [0.5], [0.5]]
    out = compute_envelope(block)
    assert 0.0 <= out <= 1.0
    assert not math.isnan(out)


# ---------------------------------------------------------------
# smooth_envelope
# ---------------------------------------------------------------


def test_smooth_envelope_snaps_when_tau_zero():
    assert smooth_envelope(0.0, 1.0, dt_s=0.033, tau_s=0.0) == 1.0   # NOSONAR  # exact representable value asserted intentionally


def test_smooth_envelope_snaps_when_dt_zero():
    """First tick after enable has dt==0 — adopt the target so the
    smoothed value isn't permanently stuck at 0."""
    assert smooth_envelope(0.0, 0.7, dt_s=0.0, tau_s=0.25) == 0.7   # NOSONAR  # exact representable value asserted intentionally


def test_smooth_envelope_approaches_target_monotonically():
    cur = 0.0
    last_gap = 1.0
    for _ in range(30):
        cur = smooth_envelope(cur, 1.0, dt_s=0.033, tau_s=0.25)
        gap = 1.0 - cur
        assert gap < last_gap
        last_gap = gap


# ---------------------------------------------------------------
# envelope_to_sway
# ---------------------------------------------------------------


def test_envelope_zero_silences_sway():
    """Silent music → no sway regardless of phase. The pet sits
    still when nothing's playing."""
    for phase in (0.0, 0.1, 0.25, 0.5, 1.0):
        out = envelope_to_sway(0.0, phase)
        assert out[PARAM_ANGLE_Z] == 0.0   # NOSONAR  # exact representable value asserted intentionally
        assert out[PARAM_BODY_ANGLE_Z] == 0.0   # NOSONAR  # exact representable value asserted intentionally


def test_envelope_one_at_phase_quarter_is_max_angle():
    """At phase = quarter-period, sin(2π · 0.25) = 1 → angle should
    reach its full configured amplitude."""
    out = envelope_to_sway(
        1.0, DEFAULT_SWAY_PERIOD_S / 4.0,
        sway_period_s=DEFAULT_SWAY_PERIOD_S,
        sway_amplitude=DEFAULT_SWAY_AMPLITUDE,
    )
    assert out[PARAM_ANGLE_Z] == pytest.approx(DEFAULT_SWAY_AMPLITUDE, abs=1e-6)


def test_envelope_body_swings_quarter_period_after_head():
    """Body lags head by 90° (cosine vs sine) so the sway reads as
    natural body motion. Catches a phase-direction regression."""
    out = envelope_to_sway(
        1.0, 0.0,
        sway_period_s=DEFAULT_SWAY_PERIOD_S,
        sway_amplitude=DEFAULT_SWAY_AMPLITUDE,
    )
    # phase=0: head sin(0)=0, body sin(π/2)=1 → body at max
    assert out[PARAM_ANGLE_Z] == pytest.approx(0.0, abs=1e-6)
    assert out[PARAM_BODY_ANGLE_Z] > 0.0


def test_envelope_clamps_above_one():
    """The mapper protects against caller-supplied envelope > 1.0
    so the swing never exceeds the configured amplitude."""
    out_clamped = envelope_to_sway(2.0, DEFAULT_SWAY_PERIOD_S / 4.0)
    out_max = envelope_to_sway(1.0, DEFAULT_SWAY_PERIOD_S / 4.0)
    assert out_clamped[PARAM_ANGLE_Z] == pytest.approx(out_max[PARAM_ANGLE_Z])


def test_envelope_zero_sway_period_is_neutral():
    """Misconfigured period (zero or negative) → return neutral
    instead of dividing by zero."""
    assert envelope_to_sway(0.5, 0.1, sway_period_s=0.0) == {
        PARAM_ANGLE_Z: 0.0, PARAM_BODY_ANGLE_Z: 0.0,
    }


def test_default_constants_in_sane_ranges():
    """Sanity guard so a future "tune the feel" PR can't ship
    nonsense defaults silently."""
    assert 0.2 <= DEFAULT_SWAY_PERIOD_S <= 2.0
    assert 0.1 <= DEFAULT_SWAY_AMPLITUDE <= 1.0
    assert 0.05 <= DEFAULT_SMOOTHING_S <= 1.0


# ---------------------------------------------------------------
# MusicRhythmDriver — Qt wrapper
# ---------------------------------------------------------------


def _doc_with_sway_params() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [
        Parameter(id=PARAM_ANGLE_Z, min=-1.0, max=1.0, default=0.0),
        Parameter(id=PARAM_BODY_ANGLE_Z, min=-1.0, max=1.0, default=0.0),
    ]
    return doc


def test_driver_starts_disabled(qapp):
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        assert driver.is_enabled() is False
        assert driver.envelope() == 0.0   # NOSONAR  # exact representable value asserted intentionally
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_with_no_document_is_noop(qapp):
    """Driver gets enabled before a rig is loaded → tick is silent,
    not a crash. Same robustness rule the other drivers follow."""
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        driver.push_envelope(0.5)
        driver.tick_once()   # no raise
        assert canvas.parameter_values() == {}
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_drives_sway_params(qapp):
    """Happy path: push a non-zero envelope, tick, the canvas's
    Z-axis params get written within range."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_sway_params())
    driver = MusicRhythmDriver(canvas)
    try:
        driver._enabled = True   # noqa: SLF001  # bypass stream open for test
        driver._phase_anchor = 0.0   # noqa: SLF001
        driver._last_tick = 0.0   # noqa: SLF001
        driver.push_envelope(1.0)
        # First tick: dt computed as a tiny positive value, smoothed
        # envelope approaches target; sway is non-zero in absolute
        # value but might be small. Run a few ticks to let smoothing
        # settle.
        for _ in range(20):
            driver.tick_once()
        values = canvas.parameter_values()
        # At least one of the two Z params should have a non-zero
        # current value once the envelope has settled toward 1.0.
        assert (
            abs(values[PARAM_ANGLE_Z])
            + abs(values[PARAM_BODY_ANGLE_Z])
            > 0.0
        )
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_push_envelope_clamps(qapp):
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        driver.push_envelope(5.0)
        assert driver._envelope_target == 1.0   # noqa: SLF001   # NOSONAR  # exact representable value asserted intentionally
        driver.push_envelope(-2.0)
        assert driver._envelope_target == 0.0   # noqa: SLF001   # NOSONAR  # exact representable value asserted intentionally
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_set_enabled_false_resets_sway_params(qapp):
    """Disable → rig settles back to neutral Z-angle rather than
    freezing mid-sway."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_sway_params())
    driver = MusicRhythmDriver(canvas)
    try:
        # Force a non-zero state by pushing parameters directly,
        # then call the reset path.
        canvas.set_parameter_values({
            PARAM_ANGLE_Z: 0.8, PARAM_BODY_ANGLE_Z: -0.3,
        })
        driver._reset_params()   # noqa: SLF001
        values = canvas.parameter_values()
        assert values[PARAM_ANGLE_Z] == 0.0   # NOSONAR  # exact representable value asserted intentionally
        assert values[PARAM_BODY_ANGLE_Z] == 0.0   # NOSONAR  # exact representable value asserted intentionally
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_set_enabled_returns_false_when_stream_open_fails(qapp, monkeypatch):
    """If the WASAPI loopback open fails (no Windows, no
    sounddevice, no output device), set_enabled must surface
    False rather than report success."""
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        monkeypatch.setattr(driver, "_open_stream", lambda: False)
        assert driver.set_enabled(True) is False
        assert driver.is_enabled() is False
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_set_enabled_idempotent_when_already_enabled(qapp, monkeypatch):
    """Second set_enabled(True) on a live driver is a no-op."""
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        monkeypatch.setattr(driver, "_open_stream", lambda: True)
        assert driver.set_enabled(True) is True
        # Open should NOT be called again — would re-init phase.
        anchor_before = driver._phase_anchor   # noqa: SLF001
        assert driver.set_enabled(True) is True
        assert driver._phase_anchor == anchor_before   # noqa: SLF001
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_shutdown_stops_timer(qapp, monkeypatch):
    canvas = PuppetCanvas()
    driver = MusicRhythmDriver(canvas)
    try:
        monkeypatch.setattr(driver, "_open_stream", lambda: True)
        driver.set_enabled(True)
        driver.shutdown()
        assert not driver._timer.isActive()   # noqa: SLF001
    finally:
        driver.deleteLater()
        canvas.deleteLater()
