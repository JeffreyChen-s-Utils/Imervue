"""Autosave must survive a torn-down canvas and stop on close.

A queued autosave tick could fire after the window closed; reading a deleted
canvas raised an uncaught RuntimeError, and the timer was never stopped. Driven
on the mixin methods unbound with fakes -- no Qt widget constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.paint.workspace_autosave import AutosaveMixin


def test_snapshot_swallows_a_dead_canvas():
    def boom():
        raise RuntimeError("Internal C++ object already deleted")

    fake = SimpleNamespace(_canvas=SimpleNamespace(document=boom))
    # A tick after the canvas is deleted must return None, not propagate.
    assert AutosaveMixin.take_autosave_snapshot_now(fake) is None


def test_stop_autosave_stops_the_timer():
    stopped: list = []
    fake = SimpleNamespace(
        _autosave_timer=SimpleNamespace(stop=lambda: stopped.append(True)))
    AutosaveMixin.stop_autosave(fake)
    assert stopped == [True]


def test_stop_autosave_is_safe_without_a_timer():
    AutosaveMixin.stop_autosave(SimpleNamespace())   # no _autosave_timer -> no raise
