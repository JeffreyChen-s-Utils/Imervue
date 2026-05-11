"""Qt-smoke for the InputEngine — toggle drag / blink / lipsync,
verify parameter values flow into the canvas without spinning real
audio capture.
"""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import Drawable, Parameter, PuppetDocument
from puppet.input_engine import InputEngine


def _doc_with_face_params() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="face", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    for pid in (
        "ParamAngleX", "ParamAngleY",
        "ParamEyeLOpen", "ParamEyeROpen",
        "ParamMouthOpenY",
    ):
        doc.parameters.append(
            Parameter(id=pid, min=-1.0, max=1.0, default=0.0, keys=[]),
        )
    return doc


# ---------------------------------------------------------------------------
# Drag tracking
# ---------------------------------------------------------------------------


def test_drag_off_by_default(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        assert engine.drag_enabled() is False
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_drag_push_cursor_writes_angle_params(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_face_params())
    engine = InputEngine(canvas)
    try:
        engine.set_drag_enabled(True)
        engine.push_cursor(100.0, 100.0)
        # Cursor at (100, 100) of a 100x100 canvas → ParamAngleX/Y == 1.0
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(1.0)
        assert canvas.parameter_values()["ParamAngleY"] == pytest.approx(1.0)
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_drag_off_ignores_cursor_pushes(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_face_params())
    engine = InputEngine(canvas)
    try:
        engine.push_cursor(100.0, 100.0)
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(0.0)
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_drag_disable_resets_angle_params(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_face_params())
    engine = InputEngine(canvas)
    try:
        engine.set_drag_enabled(True)
        engine.push_cursor(100.0, 100.0)
        engine.set_drag_enabled(False)
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(0.0)
        assert canvas.parameter_values()["ParamAngleY"] == pytest.approx(0.0)
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_drag_no_document_safe(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        engine.set_drag_enabled(True)
        engine.push_cursor(50.0, 50.0)   # must not raise
    finally:
        engine.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Blink
# ---------------------------------------------------------------------------


def test_blink_off_by_default(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        assert engine.blink_enabled() is False
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_blink_disable_restores_eye_open(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_face_params())
    engine = InputEngine(canvas)
    try:
        engine.set_blink_enabled(True)
        canvas.set_parameter_value("ParamEyeLOpen", 0.0)   # simulate mid-blink
        engine.set_blink_enabled(False)
        assert canvas.parameter_values()["ParamEyeLOpen"] == pytest.approx(1.0)
        assert canvas.parameter_values()["ParamEyeROpen"] == pytest.approx(1.0)
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_blink_state_change_signal_fires(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    captured = []
    engine.state_changed.connect(lambda: captured.append(True))
    try:
        engine.set_blink_enabled(True)
        engine.set_blink_enabled(True)   # idempotent — no extra emit
        engine.set_blink_enabled(False)
        assert len(captured) == 2
    finally:
        engine.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Lip-sync (no real mic — just verify graceful degrade)
# ---------------------------------------------------------------------------


def test_lipsync_off_by_default(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        assert engine.lipsync_enabled() is False
    finally:
        engine.deleteLater()
        canvas.deleteLater()


def test_lipsync_enable_returns_status(qapp):
    """Whether sounddevice is installed or not the call must return a
    bool — no exception ever leaks. CI typically has no mic, expect
    False; dev machines with sounddevice + a mic will return True but
    still cleanly stop."""
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        ok = engine.set_lipsync_enabled(True)
        assert isinstance(ok, bool)
        engine.set_lipsync_enabled(False)
    finally:
        engine.shutdown()
        engine.deleteLater()
        canvas.deleteLater()


def test_shutdown_safe_when_nothing_running(qapp):
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        engine.shutdown()   # should not raise even with no streams
    finally:
        engine.deleteLater()
        canvas.deleteLater()
