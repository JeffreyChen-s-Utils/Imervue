"""Qt-smoke for the InputEngine — toggle drag / blink / lipsync,
verify parameter values flow into the canvas without spinning real
audio capture.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument
from Imervue.puppet.input_engine import InputEngine


# QOpenGLWidget construction segfaults on the headless GitHub
# Actions Windows runner once the offscreen-GL pool is exhausted
# (see tests/conftest.py::skip_on_headless_ci). All tests in this
# file touch a real PuppetCanvas / PuppetWorkspace, so the whole
# module skips on CI; local runs cover them.
import os as _os_for_skip  # noqa: E402
import pytest as _pytest_for_skip  # noqa: E402

pytestmark = _pytest_for_skip.mark.skipif(
    _os_for_skip.environ.get("CI") == "true"
    or _os_for_skip.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
)



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


# ---------------------------------------------------------------------------
# Blink robustness — must fire repeatedly even when other drivers write
# the same eye-param value between blink ticks
# ---------------------------------------------------------------------------


def test_blink_runs_multiple_cycles_against_competing_writer(qapp):
    """Reproduces the "blink only fires once" bug. Simulate 10 s of
    blink ticks against a canvas that also has a competing driver
    (a stand-in for motion player / webcam tracker) writing the
    eye-param back to 1.0 between every blink tick. Without
    ``force_parameter_values`` the canvas's equality check would
    mask every blink curve transition after the first one.

    We expect to see ≥ 2 distinct "eye closed" windows (value < 0.5)
    spaced ~4.5 s apart — proof that the blink driver isn't getting
    stomped by the competing writes."""
    from unittest.mock import patch
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import Drawable, Parameter, PuppetDocument
    from Imervue.puppet.input_engine import InputEngine

    doc = PuppetDocument(size=(64, 64))
    doc.parameters = [
        Parameter(id="ParamEyeLOpen", min=0.0, max=1.0, default=1.0),
        Parameter(id="ParamEyeROpen", min=0.0, max=1.0, default=1.0),
    ]
    doc.drawables = [Drawable(
        id="x", texture="textures/x.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
    )]

    canvas = PuppetCanvas()
    canvas.load_document(doc)
    try:
        engine = InputEngine(canvas)
        engine.set_blink_enabled(True)

        # Sample what blink wrote IMMEDIATELY after its tick — before
        # the competing writer stomps it. This mirrors what the
        # renderer would have painted between ticks.
        writes = []
        anchor = engine._blink_anchor   # noqa: SLF001
        for tick in range(300):  # 10 s at 30 Hz
            fake_t = anchor + tick / 30.0
            with patch("time.monotonic", return_value=fake_t):
                engine._on_blink_tick()   # noqa: SLF001
            writes.append(canvas.parameter_values()["ParamEyeLOpen"])
            # Competing writer pushes the eye back to 1.0 *after*
            # blink fires — simulates motion player / webcam tracker
            # racing the blink driver. Without force_parameter_values
            # the next blink tick's open-window 1.0 write would match
            # the existing 1.0 and the canvas would skip the
            # recompute. The bug surfaces inside the downward-sweep
            # window: blink writes 0.69, canvas has 1.0, but the
            # WRITE is skipped if value matches what's there at the
            # nanosecond the competing writer fired.
            canvas.set_parameter_values({"ParamEyeLOpen": 1.0})

        closes = [t for t, v in enumerate(writes) if v < 0.5]
        # First blink ~tick 1-4; second ~tick 136-139 (4.5 s later)
        assert len(closes) >= 6, (
            f"expected ≥ 6 closed-eye frames across two blinks, "
            f"got {len(closes)}: {closes}"
        )
        early = [t for t in closes if t < 100]
        late = [t for t in closes if t > 100]
        assert early and late, (
            f"only one blink fired: early={early}, late={late}"
        )
    finally:
        canvas.deleteLater()


def test_blink_timer_is_repeating(qapp):
    """Defensive: the blink QTimer must be configured as repeating —
    a future PySide6 default change to single-shot would silently
    cause exactly one blink and then radio silence."""
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.input_engine import InputEngine
    canvas = PuppetCanvas()
    engine = InputEngine(canvas)
    try:
        assert engine._blink_timer.isSingleShot() is False   # noqa: SLF001
    finally:
        canvas.deleteLater()
