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


def test_the_first_tick_only_starts_the_clock(monkeypatch):
    steps = []
    host = SimpleNamespace(_physics_clock=None, step_physics=steps.append)
    times = iter([10.0, 10.016, 12.0])
    monkeypatch.setattr(canvas_mod.time, "monotonic", lambda: next(times))
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001
    assert steps == []
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001
    assert steps == [pytest.approx(0.016)]
    PuppetCanvas._on_physics_tick(host)  # noqa: SLF001 - a 2 s stall is capped
    assert steps[-1] == pytest.approx(canvas_mod._PHYSICS_MAX_DT)  # noqa: SLF001


@pytest.mark.parametrize(("chains", "visible", "running"), [
    (["hair"], True, True),
    (["hair"], False, False),
    ([], True, False),
])
def test_the_clock_runs_only_for_a_shown_rig_with_chains(qapp, chains, visible, running):
    timer = QTimer()
    host = SimpleNamespace(
        _physics=SimpleNamespace(chain_ids=lambda: chains),
        isVisible=lambda: visible, _physics_timer=timer, _physics_clock=5.0)
    try:
        PuppetCanvas._sync_physics_timer(host)  # noqa: SLF001
        assert timer.isActive() is running
        if running:
            assert host._physics_clock is None  # noqa: SLF001 - restarts cleanly
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


def test_reset_physics_returns_the_chain_to_rest():
    host, calls = _host_with_a_chain()
    host._parameter_values["In"] = 1.0  # noqa: SLF001
    PuppetCanvas.step_physics(host, 1 / 60)
    calls.clear()
    PuppetCanvas.reset_physics(host)
    assert host._physics_outputs == {}  # noqa: SLF001
    assert calls == ["recompute", "update"]
    assert host._physics.particle_positions("hair")[:, 0].tolist() == [0.0, 0.0, 0.0]  # noqa: SLF001
