"""Qt-smoke coverage for the PuppetCanvas widget.

Real GL rendering needs a display, which CI doesn't have — these tests
exercise the construction path, document binding, draw-list building,
and the pure-Python view state without forcing a paint cycle.
"""
from __future__ import annotations

import pytest

from puppet.canvas import PuppetCanvas
from puppet.document import Drawable, Parameter, PuppetDocument


def _doc_with_one_drawable() -> PuppetDocument:
    doc = PuppetDocument(size=(512, 512))
    doc.textures["textures/x.png"] = b"\x89PNG\r\n\x1a\n"   # not a real PNG, no upload happens
    doc.drawables = [
        Drawable(
            id="x", texture="textures/x.png",
            vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            indices=[0, 1, 2],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            draw_order=0,
        ),
    ]
    return doc


def _doc_with_two_parameters() -> PuppetDocument:
    """Document carrying two parameters so the batch setter has
    something to bind to. No drawables needed for batch-API tests —
    the canvas only checks that the parameter ids exist."""
    doc = _doc_with_one_drawable()
    doc.parameters = [
        Parameter(id="ParamA", min=-1.0, max=1.0, default=0.0),
        Parameter(id="ParamB", min=0.0, max=2.0, default=1.0),
    ]
    return doc


def test_canvas_constructs_without_document(qapp):
    c = PuppetCanvas()
    try:
        assert c.document() is None
        assert c.zoom_factor() == pytest.approx(1.0)
    finally:
        c.deleteLater()


def test_load_document_builds_draw_list(qapp):
    c = PuppetCanvas()
    try:
        doc = _doc_with_one_drawable()
        c.load_document(doc)
        assert c.document() is doc
        assert len(c._draw_list) == 1   # noqa: SLF001
        assert c._draw_list[0].drawable_id == "x"   # noqa: SLF001
    finally:
        c.deleteLater()


def test_load_none_clears_state(qapp):
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_one_drawable())
        c.load_document(None)
        assert c.document() is None
        assert c._draw_list == []   # noqa: SLF001
    finally:
        c.deleteLater()


def test_load_document_emits_signal(qapp):
    c = PuppetCanvas()
    try:
        captured = []
        c.document_loaded.connect(lambda: captured.append(True))
        c.load_document(_doc_with_one_drawable())
        assert captured == [True]
    finally:
        c.deleteLater()


def test_set_parameter_values_batch_updates_all(qapp):
    """Batch setter writes every recognised id in one go. The canvas
    runs only ONE vertex recompute regardless of how many params changed
    — that's the perf-relevant promise; the test here verifies the
    end-state values."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_two_parameters())
        c.set_parameter_values({"ParamA": 0.5, "ParamB": 1.5})
        values = c.parameter_values()
        assert values["ParamA"] == pytest.approx(0.5)
        assert values["ParamB"] == pytest.approx(1.5)
    finally:
        c.deleteLater()


def test_set_parameter_values_skips_unknown_keys(qapp):
    """Unknown parameter ids are silently dropped — matches the
    single-value setter's behaviour. The known ids still land."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_two_parameters())
        c.set_parameter_values({"ParamA": 0.25, "DoesNotExist": 9.0})
        values = c.parameter_values()
        assert values["ParamA"] == pytest.approx(0.25)
        assert "DoesNotExist" not in values
    finally:
        c.deleteLater()


def test_set_parameter_values_with_empty_dict_is_noop(qapp):
    """No values → no recompute, no signal, no state change."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_two_parameters())
        before = c.parameter_values()
        c.set_parameter_values({})
        assert c.parameter_values() == before
    finally:
        c.deleteLater()


def test_set_parameter_values_without_document_is_safe(qapp):
    """Called before load_document the batch setter must not raise."""
    c = PuppetCanvas()
    try:
        c.set_parameter_values({"ParamA": 1.0})   # must not throw
        assert c.parameter_values() == {}
    finally:
        c.deleteLater()


def test_set_parameter_values_no_op_when_unchanged(qapp):
    """Re-pushing the current values should not trigger another vertex
    recompute. We can't observe the internal counter directly, but we
    can sanity-check that the second call leaves state untouched."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_two_parameters())
        c.set_parameter_values({"ParamA": 0.4})
        snapshot = c.parameter_values()
        c.set_parameter_values({"ParamA": 0.4})
        assert c.parameter_values() == snapshot
    finally:
        c.deleteLater()


def test_reset_view_unlocks_user_view(qapp):
    """After programmatic ``reset_view`` the next paint is allowed to
    re-fit the puppet — used when a new document loads or the user hits
    the toolbar's Fit button."""
    c = PuppetCanvas()
    try:
        c.load_document(_doc_with_one_drawable())
        c._user_view_locked = True   # noqa: SLF001
        c.reset_view()
        assert c._user_view_locked is False   # noqa: SLF001
    finally:
        c.deleteLater()
