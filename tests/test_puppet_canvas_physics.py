"""The Puppet canvas's physics clock.

Physics chains never moved: nothing called ``step_physics``. The canvas now
steps them on a timer of its own. These run the canvas methods on small
stand-ins (no PuppetCanvas, a QOpenGLWidget), so they run on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer

from Imervue.puppet import canvas as canvas_mod
from Imervue.puppet.canvas import PuppetCanvas, _outputs_close
from Imervue.puppet.document import PhysicsParticle, PhysicsRig, PuppetDocument
from Imervue.puppet.physics import PhysicsEngine


@pytest.mark.parametrize(("new", "old", "close"), [
    ({"A": 0.5}, {"A": 0.50005}, True),
    ({"A": 0.5}, {"A": 0.5002}, False),
    ({"A": 0.5}, {}, False),
    ({}, {}, True),
    ({"A": 0.5, "B": 0.0}, {"A": 0.5}, False),
])
def test_outputs_close(new, old, close):
    assert _outputs_close(new, old) is close


_STEP = canvas_mod._PHYSICS_STEP  # noqa: SLF001


def _clock_host(monkeypatch, times):
    calls = []
    host = SimpleNamespace(
        _physics_clock=None, _physics_lag=0.0,
        step_physics=lambda dt, steps: calls.append((dt, steps)))
    ticks = iter(times)
    monkeypatch.setattr(canvas_mod.time, "monotonic", lambda: next(ticks))
    return host, calls


def test_ticks_step_in_fixed_steps_and_carry_the_rest(monkeypatch):
    host, calls = _clock_host(monkeypatch, [10.0, 10.016, 10.034, 12.0])
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001 - only starts the clock
    assert calls == []
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001 - 16 ms: not yet a step
    assert calls == []
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001 - 34 ms in all: two steps
    assert calls == [(_STEP, 2)]
    assert host._physics_lag == pytest.approx(0.034 - 2 * _STEP)  # noqa: SLF001
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001 - a 2 s stall counts as 50 ms
    assert calls[-1] == (_STEP, 3)


def test_uneven_ticks_always_step_by_the_same_length(monkeypatch):
    """Verlet takes the previous step's length as this one's: uneven dt changed the swing."""
    times, now = [], 0.0
    for gap in [0.011, 0.023, 0.016, 0.031, 0.009, 0.017] * 20:
        times.append(now)
        now += gap
    host, calls = _clock_host(monkeypatch, times)
    for _tick in times:
        PuppetCanvas._on_physics_tick(host)  # noqa: SLF001
    assert {dt for dt, _steps in calls} == {_STEP}
    assert sum(steps for _dt, steps in calls) == int(times[-1] // _STEP)


@pytest.mark.parametrize(("chains", "visible", "running"), [
    (["hair"], True, True),
    (["hair"], False, False),
    ([], True, False),
])
def test_the_clock_runs_only_for_a_shown_rig_with_chains(qapp, chains, visible, running):
    timer = QTimer()
    host = SimpleNamespace(
        _physics=SimpleNamespace(chain_ids=lambda: chains),
        isVisible=lambda: visible, _physics_timer=timer, _physics_clock=5.0,
        _physics_lag=0.01)
    try:
        PuppetCanvas._sync_physics_timer(host)  # noqa: SLF001
        assert timer.isActive() is running
        if running:
            assert host._physics_clock is None  # noqa: SLF001 - restarts cleanly
            assert host._physics_lag == pytest.approx(0.0)  # noqa: SLF001
    finally:
        timer.stop()


def _host_with_a_chain():
    doc = PuppetDocument(size=(100, 100))
    doc.physics_rigs = [PhysicsRig("hair", "In", "Out", [PhysicsParticle(), PhysicsParticle(),
                                                        PhysicsParticle()])]
    engine = PhysicsEngine()
    engine.bind_document(doc)
    calls = []
    return SimpleNamespace(
        _document=doc, _parameter_values={"In": 0.0}, _active_expressions=[],
        _physics=engine, _physics_outputs={},
        _recompute_deformed_vertices=lambda: calls.append("recompute"),
        update=lambda: calls.append("update")), calls


def test_a_moving_chain_redraws_and_a_settled_one_does_not():
    host, calls = _host_with_a_chain()
    host._parameter_values["In"] = 1.0  # noqa: SLF001
    PuppetCanvas.step_physics(host, 1 / 60)
    assert calls == ["recompute", "update"]
    assert host._physics_outputs["Out"] > 0.0  # noqa: SLF001
    for _frame in range(600):   # ten seconds: the chain settles
        PuppetCanvas.step_physics(host, 1 / 60)
    calls.clear()
    PuppetCanvas.step_physics(host, 1 / 60)
    assert calls == []


def test_several_steps_recompute_the_vertices_once():
    host, calls = _host_with_a_chain()
    host._parameter_values["In"] = 1.0  # noqa: SLF001
    PuppetCanvas.step_physics(host, 1 / 60, 3)
    assert calls == ["recompute", "update"]
    one, _calls = _host_with_a_chain()
    one._parameter_values["In"] = 1.0  # noqa: SLF001
    for _step in range(3):
        PuppetCanvas.step_physics(one, 1 / 60)
    assert host._physics_outputs == pytest.approx(one._physics_outputs)  # noqa: SLF001


def test_reset_physics_returns_the_chain_to_rest():
    host, calls = _host_with_a_chain()
    host._parameter_values["In"] = 1.0  # noqa: SLF001
    PuppetCanvas.step_physics(host, 1 / 60)
    calls.clear()
    PuppetCanvas.reset_physics(host)
    assert host._physics_outputs == {}  # noqa: SLF001
    assert calls == ["recompute", "update"]
    assert host._physics.particle_positions("hair")[:, 0].tolist() == [0.0, 0.0, 0.0]  # noqa: SLF001
