"""Closing the puppet workspace must stop every live-capture / output driver.

Webcam tracking and mic lip-sync hold OS devices open and run background
callbacks against the canvas; without a closeEvent they leaked past close (the
camera + mic stayed locked) and the mic callback fired on the deleted canvas.
The workspace now shuts every driver down on close.

Driven on ``_shutdown_drivers`` unbound on a fake -- no QMainWindow / GL widget
is constructed, so the file runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.puppet.workspace import PuppetWorkspace


def _driver(calls, name):
    return SimpleNamespace(shutdown=lambda: calls.append(name))


def test_shutdown_drivers_stops_all_four():
    calls: list = []
    ws = SimpleNamespace(
        _webcam=_driver(calls, "webcam"),
        _input_engine=_driver(calls, "input"),
        _virtual_camera=_driver(calls, "vcam"),
        _ndi_output=_driver(calls, "ndi"),
    )
    PuppetWorkspace._shutdown_drivers(ws)
    assert set(calls) == {"webcam", "input", "vcam", "ndi"}


def test_shutdown_drivers_skips_missing_and_survives_a_failure():
    calls: list = []

    def boom():
        raise RuntimeError("device already gone")

    ws = SimpleNamespace(
        _webcam=SimpleNamespace(shutdown=boom),   # raises -> suppressed
        _input_engine=_driver(calls, "input"),
        _virtual_camera=None,                     # missing -> skipped
        _ndi_output=_driver(calls, "ndi"),
    )
    PuppetWorkspace._shutdown_drivers(ws)         # must not raise
    assert calls == ["input", "ndi"]
