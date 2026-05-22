"""Tests for the mouse-gaze driver.

The driver's QTimer runs in real time, which makes wall-clock tests
flaky. We exercise the pure helpers (``gaze_target_values``,
``smoothed_value``) directly — they're stateless and take time as
input — and use ``tick_once`` to drive the Qt wrapper deterministically
without spinning the event loop.
"""
from __future__ import annotations

import math

import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument
from Imervue.puppet.mouse_gaze_driver import (
    DEFAULT_EYE_TRACK_RADIUS_PX,
    DEFAULT_HEAD_TRACK_RADIUS_PX,
    DEFAULT_SMOOTHING_S,
    MouseGazeDriver,
    gaze_target_values,
    smoothed_value,
)
from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_EYE_BALL_X,
    PARAM_EYE_BALL_Y,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Pure helpers — ``gaze_target_values``
# ---------------------------------------------------------------------------


def test_gaze_target_zero_offset_is_neutral():
    """Cursor exactly on pet center → every param zero. Anything
    else would mean the driver pushes a constant drift even when
    the user is hovering directly over the pet."""
    values = gaze_target_values((0.0, 0.0))
    assert values[PARAM_ANGLE_X] == 0.0
    assert values[PARAM_ANGLE_Y] == 0.0
    assert values[PARAM_EYE_BALL_X] == 0.0
    assert values[PARAM_EYE_BALL_Y] == 0.0


def test_gaze_target_y_axis_is_flipped():
    """Qt screen coordinates have Y-down, but Cubism convention is
    Y-up — cursor above the pet must produce *positive* angle/eye
    Y. Catching this flip is the whole reason the helper exists."""
    above = gaze_target_values((0.0, -50.0))
    below = gaze_target_values((0.0, 50.0))
    assert above[PARAM_ANGLE_Y] > 0.0
    assert below[PARAM_ANGLE_Y] < 0.0
    assert above[PARAM_EYE_BALL_Y] > 0.0
    assert below[PARAM_EYE_BALL_Y] < 0.0


def test_gaze_target_clamps_to_unit_range():
    """Cursor far outside the saturation radius must still produce
    values in ``[-1, 1]`` — pushing 1.5 into a Cubism param either
    glitches the rig or gets silently clamped by the runtime, both
    bad outcomes."""
    far_right_down = gaze_target_values((10_000.0, 10_000.0))
    far_left_up = gaze_target_values((-10_000.0, -10_000.0))
    for pid in (PARAM_ANGLE_X, PARAM_EYE_BALL_X):
        assert far_right_down[pid] == 1.0
        assert far_left_up[pid] == -1.0
    assert far_right_down[PARAM_ANGLE_Y] == -1.0   # cursor down → look down
    assert far_left_up[PARAM_ANGLE_Y] == 1.0


def test_gaze_target_eye_saturates_before_head():
    """Eyes lead, head follows — at the eye-saturation distance the
    eyes are pegged at ±1 but the head is only partway. Drop this
    and the rig looks like a turret instead of an animate puppet."""
    offset = (DEFAULT_EYE_TRACK_RADIUS_PX, 0.0)
    values = gaze_target_values(offset)
    assert values[PARAM_EYE_BALL_X] == 1.0
    assert 0.0 < values[PARAM_ANGLE_X] < 1.0


def test_gaze_target_zero_radius_returns_neutral():
    """A misconfigured caller passing ``radius_px <= 0`` must not
    produce NaN / inf. We document this as "snap to neutral" so a
    UI slider that hits zero doesn't break the live rig."""
    values = gaze_target_values(
        (100.0, 100.0), head_radius_px=0.0, eye_radius_px=0.0,
    )
    for pid in (PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_EYE_BALL_X, PARAM_EYE_BALL_Y):
        assert values[pid] == 0.0


def test_gaze_target_negative_radius_treated_as_zero():
    """Boundary: a negative radius is just as nonsensical as zero;
    same fallback path."""
    values = gaze_target_values(
        (100.0, 100.0), head_radius_px=-50.0, eye_radius_px=-1.0,
    )
    for value in values.values():
        assert value == 0.0


def test_gaze_target_returns_only_four_standard_params():
    """The driver promises it touches *only* the four look-at params;
    anything else and the contract with `_on_tick` (which iterates
    the dict and skips unknowns) gets murkier."""
    values = gaze_target_values((10.0, 10.0))
    assert set(values.keys()) == {
        PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_EYE_BALL_X, PARAM_EYE_BALL_Y,
    }


# ---------------------------------------------------------------------------
# Pure helpers — ``smoothed_value``
# ---------------------------------------------------------------------------


def test_smoothed_value_snaps_when_tau_is_zero():
    """Caller-opt-out of smoothing → adopt target immediately. This
    is what a "no smoothing" UI toggle would call into."""
    assert smoothed_value(0.0, 1.0, dt_s=0.033, tau_s=0.0) == 1.0
    assert smoothed_value(-0.5, 0.5, dt_s=0.033, tau_s=-1.0) == 0.5


def test_smoothed_value_snaps_when_dt_is_zero():
    """First tick after enable has ``dt == 0`` because we haven't
    accumulated time yet. Snap to target instead of freezing on
    stale state."""
    assert smoothed_value(0.0, 0.7, dt_s=0.0, tau_s=0.18) == 0.7


def test_smoothed_value_approaches_target_monotonically():
    """Each step should reduce the gap, never overshoot, never
    backtrack. Catches sign / alpha-formula mistakes."""
    cur = 0.0
    last_gap = 1.0
    for _ in range(20):
        cur = smoothed_value(cur, 1.0, dt_s=0.033, tau_s=0.18)
        gap = 1.0 - cur
        assert gap < last_gap
        assert gap >= 0.0
        last_gap = gap
    assert cur > 0.95   # ~20 ticks at 30 Hz easily saturates 180ms tau


def test_smoothed_value_reaches_target_after_many_tau():
    """After ``5 * tau`` worth of time we should be within ~1% of
    the target — the textbook exponential-decay convergence."""
    cur = 0.0
    target = 1.0
    tau = 0.18
    cur = smoothed_value(cur, target, dt_s=5 * tau, tau_s=tau)
    assert math.isclose(cur, target, abs_tol=0.01)


# ---------------------------------------------------------------------------
# Qt wrapper — ``MouseGazeDriver``
# ---------------------------------------------------------------------------


def _doc_with_lookat_params() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [
        Parameter(id=pid, min=-1.0, max=1.0, default=0.0)
        for pid in (
            PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_EYE_BALL_X, PARAM_EYE_BALL_Y,
        )
    ]
    return doc


def test_driver_starts_disabled(qapp):
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        assert driver.is_enabled() is False
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_enable_emits_state_changed(qapp):
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    fired: list[int] = []
    driver.state_changed.connect(lambda: fired.append(1))
    try:
        driver.set_enabled(True)
        assert driver.is_enabled() is True
        assert fired == [1]
        # Idempotent — flipping to the same state again is a no-op.
        driver.set_enabled(True)
        assert fired == [1]
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_disable_stops_signal_and_timer(qapp):
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        driver.set_enabled(True)
        driver.set_enabled(False)
        assert driver.is_enabled() is False
        assert not driver._timer.isActive()   # noqa: SLF001
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_setters_clamp_to_positive_minimum(qapp):
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        driver.set_head_radius(-100.0)
        assert driver.head_radius() >= 1.0
        driver.set_eye_radius(0.0)
        assert driver.eye_radius() >= 1.0
        driver.set_smoothing(-1.0)
        assert driver.smoothing() == 0.0
        driver.set_smoothing(0.4)
        assert driver.smoothing() == pytest.approx(0.4)
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_defaults_match_constants(qapp):
    """The driver's initial state must match the documented module
    constants — drift between them is the kind of silent bug that
    breaks tuning UIs months later."""
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        assert driver.head_radius() == DEFAULT_HEAD_TRACK_RADIUS_PX
        assert driver.eye_radius() == DEFAULT_EYE_TRACK_RADIUS_PX
        assert driver.smoothing() == DEFAULT_SMOOTHING_S
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_with_no_document_is_noop(qapp):
    """Driver enabled but no rig loaded → tick must be a silent
    no-op, never raise. The desktop-pet workflow lets users toggle
    drivers on before the first rig load."""
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        driver.set_enabled(True)
        driver.tick_once()   # no document — must not raise
        assert canvas.parameter_values() == {}
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_pushes_into_canvas_when_visible(qapp, monkeypatch):
    """Happy path: with a rig loaded and the cursor offset, the
    driver writes the four look-at parameters into the canvas."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_lookat_params())
    driver = MouseGazeDriver(canvas, canvas)
    try:
        # Force the offset directly — bypassing QCursor.pos() keeps
        # the test deterministic on machines where the cursor may be
        # anywhere on screen.
        monkeypatch.setattr(
            driver, "_cursor_offset_px",
            lambda: (DEFAULT_EYE_TRACK_RADIUS_PX, 0.0),
        )
        # Disable smoothing so one tick reaches the target — avoids
        # depending on accumulated dt across multiple ticks.
        driver.set_smoothing(0.0)
        driver.set_enabled(True)
        driver.tick_once()
        values = canvas.parameter_values()
        assert values[PARAM_EYE_BALL_X] == pytest.approx(1.0)
        assert 0.0 < values[PARAM_ANGLE_X] < 1.0
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_skips_params_missing_from_rig(qapp, monkeypatch):
    """Rig that lacks e.g. ``ParamEyeBallY`` must not crash and must
    not invent the param — same forgiving behaviour as IdleDriver."""
    canvas = PuppetCanvas()
    doc = _doc_with_lookat_params()
    doc.parameters = [p for p in doc.parameters if p.id != PARAM_EYE_BALL_Y]
    canvas.load_document(doc)
    driver = MouseGazeDriver(canvas, canvas)
    try:
        monkeypatch.setattr(
            driver, "_cursor_offset_px", lambda: (50.0, 50.0),
        )
        driver.set_smoothing(0.0)
        driver.set_enabled(True)
        driver.tick_once()
        values = canvas.parameter_values()
        assert PARAM_EYE_BALL_Y not in values
        assert PARAM_EYE_BALL_X in values
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_cursor_offset_returns_zero_for_invisible_widget(qapp):
    """When the host widget isn't on screen yet we can't compute a
    meaningful center — fall back to neutral so the rig sits still
    during the brief construction window."""
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        assert driver._cursor_offset_px() == (0.0, 0.0)   # noqa: SLF001
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_smoothed_values_round_trip_via_tick(qapp, monkeypatch):
    """``smoothed_values()`` exposes the driver's running state for
    tuning UIs. Verify it actually reflects what the tick wrote."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_lookat_params())
    driver = MouseGazeDriver(canvas, canvas)
    try:
        monkeypatch.setattr(
            driver, "_cursor_offset_px", lambda: (300.0, 0.0),
        )
        driver.set_smoothing(0.0)
        driver.set_enabled(True)
        driver.tick_once()
        snapshot = driver.smoothed_values()
        assert snapshot[PARAM_EYE_BALL_X] == pytest.approx(1.0)
        # Mutating the snapshot must not leak back into the driver.
        snapshot[PARAM_EYE_BALL_X] = -99.0
        assert driver.smoothed_values()[PARAM_EYE_BALL_X] == pytest.approx(1.0)
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_shutdown_stops_timer(qapp):
    canvas = PuppetCanvas()
    driver = MouseGazeDriver(canvas, canvas)
    try:
        driver.set_enabled(True)
        driver.shutdown()
        assert not driver._timer.isActive()   # noqa: SLF001
    finally:
        driver.deleteLater()
        canvas.deleteLater()
