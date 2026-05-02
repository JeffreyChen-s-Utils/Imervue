"""Tests for canvas-wide transforms (rotate / flip)."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import canvas_transforms as ct
from Imervue.paint.document import PaintDocument


# ---------------------------------------------------------------------------
# Pure-helper API
# ---------------------------------------------------------------------------


def test_actions_constant_lists_five_modes():
    assert set(ct.CANVAS_TRANSFORM_ACTIONS) == {
        "rotate_90_ccw", "rotate_90_cw", "rotate_180",
        "flip_horizontal", "flip_vertical",
    }


def test_rotate_90_ccw_swaps_width_and_height():
    arr = np.zeros((6, 10, 4), dtype=np.uint8)
    out = ct.rotate_90_ccw(arr)
    assert out.shape == (10, 6, 4)


def test_rotate_90_cw_swaps_width_and_height():
    arr = np.zeros((6, 10, 4), dtype=np.uint8)
    out = ct.rotate_90_cw(arr)
    assert out.shape == (10, 6, 4)


def test_rotate_180_preserves_shape():
    arr = np.zeros((6, 10, 4), dtype=np.uint8)
    out = ct.rotate_180(arr)
    assert out.shape == arr.shape


def test_rotate_180_is_double_flip():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, (6, 10, 4), dtype=np.uint8)
    np.testing.assert_array_equal(
        ct.rotate_180(arr), ct.flip_vertical(ct.flip_horizontal(arr)),
    )


def test_rotate_90_ccw_then_cw_round_trips():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, (6, 10, 4), dtype=np.uint8)
    out = ct.rotate_90_cw(ct.rotate_90_ccw(arr))
    np.testing.assert_array_equal(out, arr)


def test_flip_horizontal_mirrors_columns():
    arr = np.zeros((4, 4), dtype=np.uint8)
    arr[:, 0] = 100
    out = ct.flip_horizontal(arr)
    assert (out[:, 0] == 0).all()
    assert (out[:, -1] == 100).all()


def test_flip_vertical_mirrors_rows():
    arr = np.zeros((4, 4), dtype=np.uint8)
    arr[0, :] = 100
    out = ct.flip_vertical(arr)
    assert (out[0, :] == 0).all()
    assert (out[-1, :] == 100).all()


def test_double_flip_horizontal_is_identity():
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, (6, 8), dtype=np.uint8)
    np.testing.assert_array_equal(
        ct.flip_horizontal(ct.flip_horizontal(arr)), arr,
    )


def test_returns_contiguous_array():
    arr = np.zeros((4, 5, 4), dtype=np.uint8)
    for fn in (
        ct.rotate_90_ccw, ct.rotate_90_cw, ct.rotate_180,
        ct.flip_horizontal, ct.flip_vertical,
    ):
        out = fn(arr)
        assert out.flags["C_CONTIGUOUS"]


def test_apply_canvas_transform_dispatches():
    arr = np.zeros((4, 5, 4), dtype=np.uint8)
    out = ct.apply_canvas_transform(arr, "rotate_90_ccw")
    assert out.shape == (5, 4, 4)


def test_apply_canvas_transform_rejects_unknown_action():
    arr = np.zeros((4, 5, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="unknown canvas-transform"):
        ct.apply_canvas_transform(arr, "shear_45")


# ---------------------------------------------------------------------------
# Document integration
# ---------------------------------------------------------------------------


@pytest.fixture
def document_with_one_layer():
    doc = PaintDocument()
    base = np.zeros((6, 10, 4), dtype=np.uint8)
    base[..., 3] = 255
    base[0, :, 0] = 200   # mark the top row red
    doc.load_image(base)
    return doc


def test_document_rotate_90_ccw_swaps_shape(document_with_one_layer):
    doc = document_with_one_layer
    assert doc.shape == (6, 10)
    assert doc.transform_canvas(action="rotate_90_ccw") is True
    assert doc.shape == (10, 6)


def test_document_rotate_90_ccw_moves_top_row_to_left_column(document_with_one_layer):
    doc = document_with_one_layer
    doc.transform_canvas(action="rotate_90_ccw")
    layer = doc.active_layer()
    # The original top row (red) lands as the leftmost column after CCW.
    assert (layer.image[:, 0, 0] == 200).all()


def test_document_rotate_180_preserves_shape(document_with_one_layer):
    doc = document_with_one_layer
    doc.transform_canvas(action="rotate_180")
    assert doc.shape == (6, 10)


def test_document_flip_horizontal_keeps_shape(document_with_one_layer):
    doc = document_with_one_layer
    doc.transform_canvas(action="flip_horizontal")
    assert doc.shape == (6, 10)


def test_document_transform_carries_mask_and_selection():
    doc = PaintDocument()
    base = np.zeros((4, 6, 4), dtype=np.uint8)
    base[..., 3] = 255
    doc.load_image(base)
    layer = doc.active_layer()
    layer.mask = np.zeros((4, 6), dtype=np.uint8)
    layer.mask[0, :] = 200   # mark the top row of mask
    sel = np.zeros((4, 6), dtype=np.bool_)
    sel[0, :] = True
    doc.set_selection(sel)
    doc.transform_canvas(action="rotate_90_ccw")
    # Mask top row → left column; selection top row → left column too.
    assert (doc.active_layer().mask[:, 0] == 200).all()
    assert doc.selection() is not None
    assert doc.selection()[:, 0].all()
    assert doc.selection().shape == (6, 4)


def test_document_transform_applies_to_all_layers(document_with_one_layer):
    doc = document_with_one_layer
    doc.add_layer(name="Above")
    doc.transform_canvas(action="rotate_90_ccw")
    for layer in doc.layers():
        assert layer.image.shape == (10, 6, 4)


def test_document_transform_empty_doc_returns_false():
    doc = PaintDocument()
    assert doc.transform_canvas(action="flip_horizontal") is False


def test_document_transform_notifies_listeners(document_with_one_layer):
    doc = document_with_one_layer
    calls = []
    doc.listen(lambda: calls.append(1))
    doc.transform_canvas(action="flip_horizontal")
    assert calls


def test_document_transform_rejects_unknown_action(document_with_one_layer):
    doc = document_with_one_layer
    with pytest.raises(ValueError, match="unknown canvas-transform"):
        doc.transform_canvas(action="shear_45")
