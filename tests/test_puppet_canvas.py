"""Qt-smoke coverage for the PuppetCanvas widget.

Real GL rendering needs a display, which CI doesn't have — these tests
exercise the construction path, document binding, draw-list building,
and the pure-Python view state without forcing a paint cycle.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, Parameter, PuppetDocument

from _qt_skip import pytestmark  # noqa: E402,F401


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


# ---------------------------------------------------------------------------
# Premultiplied-alpha texture upload helper
# ---------------------------------------------------------------------------


def test_premultiply_alpha_zeros_rgb_on_fully_transparent_pixels():
    """A pixel with alpha=0 should end up with RGB=0 regardless of its
    authored colour. This is the fix for the Cubism-atlas white halo —
    transparent edge pixels stop leaking their white background into
    GL_LINEAR interpolation."""
    import numpy as np
    from Imervue.puppet.canvas import _premultiply_alpha
    src = np.array([[
        [255, 255, 255, 0],   # white but fully transparent → must zero out
        [200, 100,  50, 255], # fully opaque → unchanged
    ]], dtype=np.uint8)
    out = _premultiply_alpha(src)
    assert tuple(out[0, 0]) == (0, 0, 0, 0)
    assert tuple(out[0, 1]) == (200, 100, 50, 255)


def test_premultiply_alpha_scales_partial_alpha_correctly():
    """Mid-alpha pixels should have RGB scaled by alpha/255 with
    proper rounding (``(rgb * alpha + 127) // 255``)."""
    import numpy as np
    from Imervue.puppet.canvas import _premultiply_alpha
    src = np.array([[[200, 100, 50, 128]]], dtype=np.uint8)   # alpha ~ 0.5
    out = _premultiply_alpha(src)
    # Expected: 200 * 128 / 255 ≈ 100, 100 * 128 / 255 ≈ 50, 50 * 128/255 ≈ 25
    assert tuple(out[0, 0]) == (100, 50, 25, 128)


def test_premultiply_alpha_rejects_wrong_shape():
    """Helper is documented as H×W×4 uint8; other shapes / dtypes must
    raise rather than silently corrupt the texture upload."""
    import numpy as np
    import pytest
    from Imervue.puppet.canvas import _premultiply_alpha
    with pytest.raises(ValueError):
        _premultiply_alpha(np.zeros((4, 4), dtype=np.uint8))
    with pytest.raises(ValueError):
        _premultiply_alpha(np.zeros((4, 4, 3), dtype=np.uint8))
    with pytest.raises(ValueError):
        _premultiply_alpha(np.zeros((4, 4, 4), dtype=np.float32))
