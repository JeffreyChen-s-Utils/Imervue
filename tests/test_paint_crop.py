"""Tests for the crop helpers + the PaintDocument crop wiring."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.crop import (
    crop_to_rect,
    non_transparent_bounds,
    selection_bounds,
    union_bounds,
)
from Imervue.paint.document import PaintDocument


# ---------------------------------------------------------------------------
# crop_to_rect
# ---------------------------------------------------------------------------


def test_crop_to_rect_returns_slice():
    arr = np.arange(100, dtype=np.uint8).reshape(10, 10)
    out = crop_to_rect(arr, (2, 3, 4, 5))
    assert out.shape == (5, 4)
    assert out[0, 0] == arr[3, 2]


def test_crop_to_rect_returns_contiguous_array():
    arr = np.zeros((10, 10, 4), dtype=np.uint8)
    out = crop_to_rect(arr, (0, 0, 5, 5))
    assert out.flags["C_CONTIGUOUS"]


def test_crop_to_rect_clamps_overshoot():
    arr = np.zeros((10, 10), dtype=np.uint8)
    out = crop_to_rect(arr, (5, 5, 100, 100))
    assert out.shape == (5, 5)


def test_crop_to_rect_rejects_zero_dimensions():
    arr = np.zeros((10, 10), dtype=np.uint8)
    with pytest.raises(ValueError, match="positive"):
        crop_to_rect(arr, (0, 0, 0, 5))


def test_crop_to_rect_rejects_no_overlap():
    arr = np.zeros((10, 10), dtype=np.uint8)
    with pytest.raises(ValueError, match="does not overlap"):
        crop_to_rect(arr, (-100, 0, 5, 5))


def test_crop_to_rect_rejects_1d():
    with pytest.raises(ValueError, match="2-D"):
        crop_to_rect(np.zeros(10, dtype=np.uint8), (0, 0, 5, 5))


def test_crop_to_rect_works_on_3d_image():
    arr = np.zeros((10, 10, 4), dtype=np.uint8)
    arr[0, 0] = (200, 100, 50, 255)
    out = crop_to_rect(arr, (0, 0, 5, 5))
    assert out.shape == (5, 5, 4)
    assert tuple(out[0, 0]) == (200, 100, 50, 255)


# ---------------------------------------------------------------------------
# selection_bounds
# ---------------------------------------------------------------------------


def test_selection_bounds_returns_bbox():
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[2:5, 3:7] = True
    rect = selection_bounds(sel)
    assert rect == (3, 2, 4, 3)   # (x, y, w, h)


def test_selection_bounds_empty_returns_none():
    sel = np.zeros((10, 10), dtype=np.bool_)
    assert selection_bounds(sel) is None


def test_selection_bounds_single_pixel():
    sel = np.zeros((10, 10), dtype=np.bool_)
    sel[5, 7] = True
    assert selection_bounds(sel) == (7, 5, 1, 1)


def test_selection_bounds_rejects_non_bool():
    sel = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        selection_bounds(sel)


# ---------------------------------------------------------------------------
# non_transparent_bounds
# ---------------------------------------------------------------------------


def test_non_transparent_bounds_returns_alpha_bbox():
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    img[2:5, 3:7, 3] = 255
    rect = non_transparent_bounds(img)
    assert rect == (3, 2, 4, 3)


def test_non_transparent_bounds_fully_transparent_returns_none():
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    assert non_transparent_bounds(img) is None


def test_non_transparent_bounds_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        non_transparent_bounds(rgb)


# ---------------------------------------------------------------------------
# union_bounds
# ---------------------------------------------------------------------------


def test_union_bounds_combines_two_rects():
    a = (0, 0, 5, 5)
    b = (10, 10, 5, 5)
    assert union_bounds(a, b) == (0, 0, 15, 15)


def test_union_bounds_skips_none_entries():
    # (1, 2, 3, 4) covers x ∈ [1, 4), y ∈ [2, 6); (10, 10, 1, 1) covers
    # x ∈ [10, 11), y ∈ [10, 11). Union: x ∈ [1, 11), y ∈ [2, 11).
    assert union_bounds((1, 2, 3, 4), None, (10, 10, 1, 1)) == (1, 2, 10, 9)


def test_union_bounds_all_none_returns_none():
    assert union_bounds(None, None) is None


def test_union_bounds_no_args_returns_none():
    assert union_bounds() is None


# ---------------------------------------------------------------------------
# Document.crop / crop_to_selection / crop_to_non_transparent
# ---------------------------------------------------------------------------


@pytest.fixture
def document_with_padded_content():
    doc = PaintDocument()
    base = np.zeros((20, 20, 4), dtype=np.uint8)
    base[5:15, 5:15, :3] = (200, 100, 50)
    base[5:15, 5:15, 3] = 255
    doc.load_image(base)
    return doc


def test_document_crop_resizes_layers(document_with_padded_content):
    doc = document_with_padded_content
    assert doc.crop((5, 5, 10, 10)) is True
    assert doc.shape == (10, 10)
    assert tuple(doc.active_layer().image[0, 0]) == (200, 100, 50, 255)


def test_document_crop_resizes_selection_too(document_with_padded_content):
    doc = document_with_padded_content
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    doc.set_selection(sel)
    doc.crop((5, 5, 10, 10))
    assert doc.selection() is not None
    assert doc.selection().shape == (10, 10)
    assert doc.selection().all()


def test_document_crop_resizes_layer_mask(document_with_padded_content):
    doc = document_with_padded_content
    layer = doc.active_layer()
    layer.mask = np.zeros((20, 20), dtype=np.uint8)
    layer.mask[5:15, 5:15] = 255
    doc.crop((5, 5, 10, 10))
    assert doc.active_layer().mask.shape == (10, 10)
    assert (doc.active_layer().mask == 255).all()


def test_document_crop_to_selection(document_with_padded_content):
    doc = document_with_padded_content
    sel = np.zeros((20, 20), dtype=np.bool_)
    sel[5:15, 5:15] = True
    doc.set_selection(sel)
    assert doc.crop_to_selection() is True
    assert doc.shape == (10, 10)


def test_document_crop_to_selection_no_selection_returns_false():
    doc = PaintDocument()
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    doc.load_image(base)
    assert doc.crop_to_selection() is False


def test_document_crop_to_selection_empty_selection_returns_false():
    doc = PaintDocument()
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    doc.load_image(base)
    doc.set_selection(np.zeros((10, 10), dtype=np.bool_))
    assert doc.crop_to_selection() is False


def test_document_crop_to_non_transparent_trims_padding(document_with_padded_content):
    doc = document_with_padded_content
    assert doc.crop_to_non_transparent() is True
    # Original opaque region was 5..15 → 10x10 after crop.
    assert doc.shape == (10, 10)


def test_document_crop_to_non_transparent_fully_transparent_returns_false():
    doc = PaintDocument()
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    doc.load_image(base)
    assert doc.crop_to_non_transparent() is False


def test_document_crop_notifies_listeners(document_with_padded_content):
    doc = document_with_padded_content
    calls = []
    doc.listen(lambda: calls.append(1))
    doc.crop((0, 0, 10, 10))
    assert calls
