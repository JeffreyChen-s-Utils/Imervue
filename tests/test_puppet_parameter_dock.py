"""Qt-smoke coverage for the ParameterDock + canvas integration.

The dock owns one slider per parameter; moving a slider pushes a value
into the bound canvas, the canvas recomputes deformed vertices, and
the dock listens for ``parameters_changed`` so a fresh document load
or a programmatic reset re-syncs sliders.
"""
from __future__ import annotations
import math

import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Deformer,
    Drawable,
    Parameter,
    ParameterKey,
    PuppetDocument,
)
from Imervue.puppet.parameter_dock import ParameterDock

from _qt_skip import pytestmark  # noqa: E402,F401


def _rigged_doc() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="face", texture="textures/x.png",
            vertices=[(50.0, 0.0)],
            indices=[],
            uvs=[(0.0, 0.0)],
            draw_order=0,
        ),
    ]
    doc.deformers = [
        Deformer(
            id="rot", type="rotation", parent=None, drawables=["face"],
            form={"anchor": [50.0, 50.0], "angle": 0.0},
        ),
    ]
    doc.parameters = [
        Parameter(
            id="ParamAngleX", min=-1.0, max=1.0, default=0.0,
            keys=[
                ParameterKey(value=-1.0, forms={"rot": {"angle": -math.pi / 2}}),
                ParameterKey(value=1.0, forms={"rot": {"angle": math.pi / 2}}),
            ],
        ),
    ]
    return doc


# ---------------------------------------------------------------------------
# Rebuild logic
# ---------------------------------------------------------------------------


def test_dock_shows_empty_state_with_no_document(qapp):
    canvas = PuppetCanvas()
    dock = ParameterDock(canvas)
    try:
        # No sliders, no value labels — only the empty placeholder
        assert dock._sliders == {}   # noqa: SLF001
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_builds_one_slider_per_parameter(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    dock = ParameterDock(canvas)
    try:
        assert "ParamAngleX" in dock._sliders   # noqa: SLF001
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_resyncs_when_document_swapped(qapp):
    canvas = PuppetCanvas()
    dock = ParameterDock(canvas)
    try:
        canvas.load_document(_rigged_doc())
        # Replace the document with one that has a different parameter
        new_doc = _rigged_doc()
        new_doc.parameters[0] = Parameter(
            id="ParamMouthOpen", min=0.0, max=1.0, default=0.0, keys=[],
        )
        canvas.load_document(new_doc)
        assert "ParamMouthOpen" in dock._sliders   # noqa: SLF001
        assert "ParamAngleX" not in dock._sliders   # noqa: SLF001
    finally:
        dock.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Slider drives canvas
# ---------------------------------------------------------------------------


def test_slider_change_updates_canvas_parameter_value(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    dock = ParameterDock(canvas)
    try:
        slider = dock.slider_for("ParamAngleX")
        # Slider step at maximum → parameter value at param.max (= 1.0)
        slider.setValue(slider.maximum())
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(1.0)
        # And at min step → param.min (= -1.0)
        slider.setValue(slider.minimum())
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(-1.0)
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_slider_change_emits_value_changed_signal(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    dock = ParameterDock(canvas)
    captured: list = []
    dock.value_changed.connect(lambda pid, v: captured.append((pid, v)))
    try:
        slider = dock.slider_for("ParamAngleX")
        # Default sits at the middle step (param default 0.0 in [-1, 1]);
        # nudge to a clearly different position so valueChanged fires.
        slider.setValue(slider.maximum())
        assert captured
        param_id, value = captured[-1]
        assert param_id == "ParamAngleX"
        # Slider at max → param.max
        assert value == pytest.approx(1.0)
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_slider_drives_deformed_vertices(qapp):
    """Sliding the parameter moves the actual vertex positions the
    canvas would draw — proves the runtime pipeline reaches the GL
    side."""
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    dock = ParameterDock(canvas)
    try:
        # Snapshot neutral verts
        neutral = canvas._deformed_vertices["face"].copy()   # noqa: SLF001
        # Drag slider all the way right (param value → 1.0 → 90° rotation)
        slider = dock.slider_for("ParamAngleX")
        slider.setValue(slider.maximum())
        rotated = canvas._deformed_vertices["face"]   # noqa: SLF001
        # Vertex (50, 0) → (100, 50) under 90° CCW around (50, 50)
        assert rotated[0, 0] != neutral[0, 0]
        assert rotated[0, 1] != neutral[0, 1]
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_reset_button_restores_defaults(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    dock = ParameterDock(canvas)
    try:
        slider = dock.slider_for("ParamAngleX")
        slider.setValue(slider.maximum())
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(1.0)
        # Programmatic reset (matches the "Reset all" button)
        canvas.reset_parameters()
        assert canvas.parameter_values()["ParamAngleX"] == pytest.approx(0.0)
    finally:
        dock.deleteLater()
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------------


def test_canvas_load_document_seeds_default_parameter_values(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_rigged_doc())
        assert canvas.parameter_values() == {"ParamAngleX": 0.0}
    finally:
        canvas.deleteLater()


def test_canvas_set_parameter_unknown_id_is_silent(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_rigged_doc())
    try:
        # Should not raise, just no-op
        canvas.set_parameter_value("ParamMissing", 0.5)
        assert "ParamMissing" not in canvas.parameter_values()
    finally:
        canvas.deleteLater()


def test_canvas_set_parameter_with_no_document_is_safe(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.set_parameter_value("anything", 1.0)
    finally:
        canvas.deleteLater()
