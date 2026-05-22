"""Tests for the idle-minigame driver.

The driver's escalation is time-based; we freeze ``time.monotonic``
via monkeypatch so the stage transitions are deterministic
without sleeping in the test.
"""
from __future__ import annotations

import pytest

from Imervue.desktop_pet import idle_minigame
from Imervue.desktop_pet.idle_minigame import (
    DEFAULT_CURIOUS_THRESHOLD_S,
    DEFAULT_GAZE_RANGE,
    DEFAULT_SLEEP_THRESHOLD_S,
    DEFAULT_YAWN_THRESHOLD_S,
    SLEEP_MOTION_GROUP,
    YAWN_MOTION_GROUP,
    IdleMinigameDriver,
    IdleStage,
    pick_phantom_offset,
    stage_for_idle,
)
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument
from Imervue.puppet.standard_params import (
    PARAM_ANGLE_X,
    PARAM_ANGLE_Y,
    PARAM_EYE_BALL_X,
    PARAM_EYE_BALL_Y,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------
# stage_for_idle
# ---------------------------------------------------------------


def test_stage_active_under_curious_threshold():
    assert stage_for_idle(0.0) is IdleStage.ACTIVE
    assert stage_for_idle(5.0) is IdleStage.ACTIVE
    assert stage_for_idle(
        DEFAULT_CURIOUS_THRESHOLD_S - 0.1,
    ) is IdleStage.ACTIVE


def test_stage_curious_between_thresholds():
    assert stage_for_idle(DEFAULT_CURIOUS_THRESHOLD_S) is IdleStage.CURIOUS
    assert stage_for_idle(
        DEFAULT_YAWN_THRESHOLD_S - 0.1,
    ) is IdleStage.CURIOUS


def test_stage_yawn_between_yawn_and_sleep():
    assert stage_for_idle(DEFAULT_YAWN_THRESHOLD_S) is IdleStage.YAWN
    assert stage_for_idle(
        DEFAULT_SLEEP_THRESHOLD_S - 0.1,
    ) is IdleStage.YAWN


def test_stage_sleep_at_and_above_threshold():
    assert stage_for_idle(DEFAULT_SLEEP_THRESHOLD_S) is IdleStage.SLEEP
    assert stage_for_idle(DEFAULT_SLEEP_THRESHOLD_S + 100.0) is IdleStage.SLEEP


def test_stage_custom_thresholds():
    """Tuning UI use-case: lower thresholds for impatient pets."""
    assert stage_for_idle(
        2.0, curious_threshold=1.0, yawn_threshold=10.0, sleep_threshold=20.0,
    ) is IdleStage.CURIOUS


# ---------------------------------------------------------------
# pick_phantom_offset
# ---------------------------------------------------------------


def test_pick_phantom_offset_returns_four_params():
    out = pick_phantom_offset(random_unit=(0.5, -0.5))
    assert set(out.keys()) == {
        PARAM_ANGLE_X, PARAM_ANGLE_Y, PARAM_EYE_BALL_X, PARAM_EYE_BALL_Y,
    }


def test_pick_phantom_offset_within_range():
    """No param should exceed the gaze range on the head, or 1.0
    on the eyes. Catches a future refactor that drops a clamp."""
    for ux in (-1.0, -0.3, 0.0, 0.3, 1.0):
        for uy in (-1.0, 0.0, 1.0):
            out = pick_phantom_offset(
                random_unit=(ux, uy), gaze_range=DEFAULT_GAZE_RANGE,
            )
            assert abs(out[PARAM_ANGLE_X]) <= DEFAULT_GAZE_RANGE + 1e-9
            assert abs(out[PARAM_ANGLE_Y]) <= DEFAULT_GAZE_RANGE + 1e-9
            assert abs(out[PARAM_EYE_BALL_X]) <= 1.0 + 1e-9
            assert abs(out[PARAM_EYE_BALL_Y]) <= 1.0 + 1e-9


def test_pick_phantom_offset_eyes_lead_head():
    """Eyes scale 1.5× harder than the head so the rig looks
    natural — eyes catch the target before the neck turns."""
    out = pick_phantom_offset(random_unit=(0.5, 0.5))
    # At ux=0.5 with range 0.55, head_x = 0.275.
    # Eye is 0.5 * 1.5 = 0.75, larger in magnitude.
    assert abs(out[PARAM_EYE_BALL_X]) > abs(out[PARAM_ANGLE_X])


def test_pick_phantom_offset_clamps_input():
    """A misconfigured caller passing |u| > 1 → clamped to ±1."""
    out = pick_phantom_offset(random_unit=(5.0, -5.0))
    # Eye saturates at 1.0 (clamp), head at gaze_range.
    assert out[PARAM_EYE_BALL_X] == 1.0   # NOSONAR  # exact representable value asserted intentionally
    assert out[PARAM_EYE_BALL_Y] == -1.0   # NOSONAR  # exact representable value asserted intentionally
    assert out[PARAM_ANGLE_X] == pytest.approx(DEFAULT_GAZE_RANGE)
    assert out[PARAM_ANGLE_Y] == pytest.approx(-DEFAULT_GAZE_RANGE)


def test_pick_phantom_offset_default_random_is_in_range():
    """Without ``random_unit``, the helper draws from secrets.
    Just sanity check the result stays in range over many draws."""
    for _ in range(20):
        out = pick_phantom_offset()
        assert -DEFAULT_GAZE_RANGE <= out[PARAM_ANGLE_X] <= DEFAULT_GAZE_RANGE
        assert -1.0 <= out[PARAM_EYE_BALL_X] <= 1.0


# ---------------------------------------------------------------
# IdleMinigameDriver
# ---------------------------------------------------------------


def _doc_with_gaze_params() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
        draw_order=0,
    )]
    doc.parameters = [
        Parameter(id=PARAM_ANGLE_X, min=-1.0, max=1.0, default=0.0),
        Parameter(id=PARAM_ANGLE_Y, min=-1.0, max=1.0, default=0.0),
        Parameter(id=PARAM_EYE_BALL_X, min=-1.0, max=1.0, default=0.0),
        Parameter(id=PARAM_EYE_BALL_Y, min=-1.0, max=1.0, default=0.0),
    ]
    return doc


def test_driver_starts_active(qapp):
    canvas = PuppetCanvas()
    driver = IdleMinigameDriver(canvas)
    try:
        assert driver.stage() is IdleStage.ACTIVE
        assert driver.is_enabled() is False
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_stage_transitions_through_thresholds(qapp, monkeypatch):
    """Drive the clock forward and verify each stage transition
    fires in order with the right signal value."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_gaze_params())
    driver = IdleMinigameDriver(canvas)
    try:
        now = [1000.0]
        monkeypatch.setattr(
            idle_minigame.time, "monotonic", lambda: now[0],
        )
        emitted: list[str] = []
        driver.stage_changed.connect(emitted.append)
        driver.set_enabled(True)
        # ACTIVE → no transition signal beyond initial state.
        driver.tick_once()
        # Cross into CURIOUS.
        now[0] = 1000.0 + DEFAULT_CURIOUS_THRESHOLD_S + 0.5
        driver.tick_once()
        assert driver.stage() is IdleStage.CURIOUS
        # Cross into YAWN.
        now[0] = 1000.0 + DEFAULT_YAWN_THRESHOLD_S + 0.5
        driver.tick_once()
        assert driver.stage() is IdleStage.YAWN
        # Cross into SLEEP.
        now[0] = 1000.0 + DEFAULT_SLEEP_THRESHOLD_S + 0.5
        driver.tick_once()
        assert driver.stage() is IdleStage.SLEEP
        # Stage transitions emitted in order.
        assert "curious" in emitted
        assert "yawn" in emitted
        assert "sleep" in emitted
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_notify_activity_resets_to_active(qapp, monkeypatch):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_gaze_params())
    driver = IdleMinigameDriver(canvas)
    try:
        now = [1000.0]
        monkeypatch.setattr(
            idle_minigame.time, "monotonic", lambda: now[0],
        )
        driver.set_enabled(True)
        now[0] = 1000.0 + DEFAULT_CURIOUS_THRESHOLD_S + 0.5
        driver.tick_once()
        assert driver.stage() is IdleStage.CURIOUS
        # User comes back.
        driver.notify_activity()
        assert driver.stage() is IdleStage.ACTIVE
        assert driver.idle_seconds() == 0.0   # NOSONAR  # exact representable value asserted intentionally
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_yawn_motion_fires_once_per_visit(qapp, monkeypatch):
    """Re-entering YAWN from within the same idle session must not
    re-trigger the motion. Otherwise crossing back and forth would
    spam the Yawn group."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_gaze_params())
    driver = IdleMinigameDriver(canvas)
    try:
        now = [1000.0]
        monkeypatch.setattr(
            idle_minigame.time, "monotonic", lambda: now[0],
        )
        played: list[str] = []
        driver.set_motion_callback(played.append)
        driver.set_enabled(True)
        # Cross into YAWN twice (re-tick at the same time).
        now[0] = 1000.0 + DEFAULT_YAWN_THRESHOLD_S + 0.5
        driver.tick_once()
        driver.tick_once()
        assert played == [YAWN_MOTION_GROUP]
        # Then SLEEP fires once.
        now[0] = 1000.0 + DEFAULT_SLEEP_THRESHOLD_S + 0.5
        driver.tick_once()
        assert played == [YAWN_MOTION_GROUP, SLEEP_MOTION_GROUP]
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_motion_callback_failure_does_not_crash(qapp, monkeypatch):
    """A misbehaving motion callback must not take the driver
    down with it."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_gaze_params())
    driver = IdleMinigameDriver(canvas)
    try:
        now = [1000.0]
        monkeypatch.setattr(
            idle_minigame.time, "monotonic", lambda: now[0],
        )

        def boom(_group):
            raise RuntimeError("rig blew up")

        driver.set_motion_callback(boom)
        driver.set_enabled(True)
        now[0] = 1000.0 + DEFAULT_YAWN_THRESHOLD_S + 0.5
        driver.tick_once()   # no raise
        assert driver.stage() is IdleStage.YAWN
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_disable_resets_gaze_to_neutral(qapp):
    """Toggling off must settle the rig — otherwise the puppet
    stays mid-glance forever."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_gaze_params())
    canvas.set_parameter_values({
        PARAM_ANGLE_X: 0.5, PARAM_EYE_BALL_X: -0.4,
    })
    driver = IdleMinigameDriver(canvas)
    try:
        driver.set_enabled(True)
        driver.set_enabled(False)
        values = canvas.parameter_values()
        assert values[PARAM_ANGLE_X] == 0.0   # NOSONAR  # exact representable value asserted intentionally
        assert values[PARAM_EYE_BALL_X] == 0.0   # NOSONAR  # exact representable value asserted intentionally
    finally:
        driver.deleteLater()
        canvas.deleteLater()


def test_tick_with_no_document_is_noop(qapp):
    """Driver enabled before a rig is loaded → silent."""
    canvas = PuppetCanvas()
    driver = IdleMinigameDriver(canvas)
    try:
        driver.set_enabled(True)
        driver.tick_once()   # must not raise
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()


def test_set_enabled_idempotent(qapp):
    canvas = PuppetCanvas()
    driver = IdleMinigameDriver(canvas)
    try:
        driver.set_enabled(True)
        anchor = driver._last_activity   # noqa: SLF001
        driver.set_enabled(True)   # second call — no-op
        assert driver._last_activity == anchor   # noqa: SLF001
    finally:
        driver.set_enabled(False)
        driver.deleteLater()
        canvas.deleteLater()
