"""Tests for the idle auto-driver — pure math helpers + the Qt
``IdleDriver`` wrapper.

Curve helpers are deterministic functions of time, so happy / boundary /
defensive cases are all checkable without Qt. The wrapper test under
``qapp`` only verifies the on/off plumbing — the actual per-tick
parameter writes are exercised by integration tests of the canvas.
"""
from __future__ import annotations

import math

import pytest

from puppet.idle_driver import (
    BREATH_PERIOD_S,
    DRIFT_AMPLITUDE,
    DRIFT_PERIODS,
    IdleDriver,
    breath_curve_value,
    idle_drift_value,
    idle_parameter_values,
)
from puppet.standard_params import PARAM_ANGLE_X, PARAM_BREATH


# ---------------------------------------------------------------------------
# breath_curve_value
# ---------------------------------------------------------------------------


def test_breath_starts_at_full_exhale():
    assert breath_curve_value(0.0) == pytest.approx(0.0, abs=1e-9)


def test_breath_peaks_at_midpoint():
    assert breath_curve_value(BREATH_PERIOD_S / 2.0) == pytest.approx(1.0, abs=1e-9)


def test_breath_returns_to_exhale_at_full_period():
    assert breath_curve_value(BREATH_PERIOD_S) == pytest.approx(0.0, abs=1e-9)


def test_breath_stays_in_unit_range():
    samples = [breath_curve_value(t * 0.1) for t in range(200)]
    assert all(0.0 - 1e-9 <= s <= 1.0 + 1e-9 for s in samples)


def test_breath_non_positive_period_returns_neutral():
    assert breath_curve_value(1.0, period=0.0) == pytest.approx(0.5)
    assert breath_curve_value(1.0, period=-3.0) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# idle_drift_value
# ---------------------------------------------------------------------------


def test_drift_starts_at_zero():
    assert idle_drift_value(0.0, period=10.0) == pytest.approx(0.0)


def test_drift_amplitude_is_respected():
    samples = [idle_drift_value(t * 0.1, period=4.0, amplitude=0.2) for t in range(200)]
    assert max(samples) <= 0.2 + 1e-9
    assert min(samples) >= -0.2 - 1e-9


def test_drift_phase_offset_shifts_curve():
    base = idle_drift_value(0.0, period=4.0)
    shifted = idle_drift_value(0.0, period=4.0, phase_offset=math.pi / 2.0)
    assert base != pytest.approx(shifted)


def test_drift_non_positive_period_returns_zero():
    assert idle_drift_value(1.0, period=0.0) == 0.0
    assert idle_drift_value(1.0, period=-1.0) == 0.0


# ---------------------------------------------------------------------------
# idle_parameter_values aggregate
# ---------------------------------------------------------------------------


def test_idle_parameter_values_includes_breath_and_drift_ids():
    out = idle_parameter_values(1.5)
    assert PARAM_BREATH in out
    for drift_id in DRIFT_PERIODS:
        assert drift_id in out


def test_idle_parameter_values_bounded():
    out = idle_parameter_values(2.7)
    assert 0.0 <= out[PARAM_BREATH] <= 1.0
    for param_id, value in out.items():
        if param_id == PARAM_BREATH:
            continue
        assert abs(value) <= DRIFT_AMPLITUDE + 1e-9


# ---------------------------------------------------------------------------
# IdleDriver Qt wrapper smoke
# ---------------------------------------------------------------------------


class _FakeCanvas:
    """Stand-in for PuppetCanvas — only implements what IdleDriver
    actually calls, so the test stays Qt-OpenGL-free."""

    def __init__(self):
        self._params = {PARAM_BREATH: 0.0, PARAM_ANGLE_X: 0.0}
        self.writes: list[tuple[str, float]] = []
        self._doc = object()   # sentinel — IdleDriver only checks for None

    def document(self):
        return self._doc

    def parameter_values(self):
        return dict(self._params)

    def set_parameter_value(self, param_id: str, value: float) -> None:
        self._params[param_id] = float(value)
        self.writes.append((param_id, float(value)))


def test_idle_driver_starts_disabled(qapp):
    canvas = _FakeCanvas()
    driver = IdleDriver(canvas)
    try:
        assert driver.is_enabled() is False
    finally:
        driver.shutdown()
        driver.deleteLater()


def test_idle_driver_set_enabled_toggles_state(qapp):
    canvas = _FakeCanvas()
    driver = IdleDriver(canvas)
    try:
        driver.set_enabled(True)
        assert driver.is_enabled() is True
        driver.set_enabled(False)
        assert driver.is_enabled() is False
    finally:
        driver.shutdown()
        driver.deleteLater()


def test_idle_driver_tick_writes_only_known_parameters(qapp):
    canvas = _FakeCanvas()
    driver = IdleDriver(canvas)
    try:
        driver.set_enabled(True)
        driver._on_tick()   # noqa: SLF001 — direct tick for determinism
        written = {p for p, _ in canvas.writes}
        # Breath and ParamAngleX are in the fake's known list; the rest
        # of the drift ids aren't, so they MUST be filtered out.
        assert PARAM_BREATH in written
        assert PARAM_ANGLE_X in written
        for unknown in ("ParamAngleY", "ParamBodyAngleX"):
            assert unknown not in written
    finally:
        driver.shutdown()
        driver.deleteLater()
