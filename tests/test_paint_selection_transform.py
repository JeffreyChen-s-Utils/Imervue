"""Tests for affine transform of selected layer pixels."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.selection_transform import transform_selection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_layer(h=20, w=20, fill_alpha=0):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 3] = fill_alpha
    return img


def _box_selection(shape, y0, y1, x0, x1):
    h, w = shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[y0:y1, x0:x1] = True
    return sel


# ---------------------------------------------------------------------------
# Pure helper — transform_selection
# ---------------------------------------------------------------------------


def test_identity_returns_inputs_unchanged():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 5, 10, 5, 10)
    out_img, out_sel = transform_selection(img, sel)
    np.testing.assert_array_equal(out_img, img)
    np.testing.assert_array_equal(out_sel, sel)


def test_empty_selection_is_noop():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 0, 0, 0, 0)   # empty
    out_img, out_sel = transform_selection(img, sel, dx=5)
    np.testing.assert_array_equal(out_img, img)
    np.testing.assert_array_equal(out_sel, sel)


def test_translation_moves_selected_pixels_right():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 5, 10, 5, 10)
    out_img, out_sel = transform_selection(img, sel, dx=5)
    # Original location is now transparent (alpha 0).
    assert out_img[7, 6, 3] == 0
    # New location (shifted right by 5) is red.
    assert tuple(out_img[7, 11]) == (255, 0, 0, 255)
    # Selection mask shifted accordingly.
    assert out_sel[7, 11]
    assert not out_sel[7, 6]


def test_translation_off_canvas_drops_pixels():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 5, 10, 5, 10)
    out_img, out_sel = transform_selection(img, sel, dx=100)
    # Everything fell off the right edge.
    assert out_img[..., 3].sum() == 0
    assert not out_sel.any()


def test_180_degree_rotation_preserves_pixel_count():
    img = _make_layer(h=20, w=20)
    img[8:13, 8:13, :] = (50, 200, 100, 255)
    sel = _box_selection(img.shape[:2], 8, 13, 8, 13)
    original_sum = sel.sum()
    out_img, out_sel = transform_selection(img, sel, angle_deg=180.0)
    # Count of selected pixels should be approximately preserved.
    assert abs(int(out_sel.sum()) - int(original_sum)) <= 4


def test_uniform_scale_grows_selection():
    img = _make_layer(h=40, w=40)
    img[18:23, 18:23, :] = (200, 50, 50, 255)
    sel = _box_selection(img.shape[:2], 18, 23, 18, 23)
    out_img, out_sel = transform_selection(img, sel, scale=2.0)
    # 2x scale → ~4x pixel count (within bilinear-edge slop).
    assert out_sel.sum() > sel.sum() * 3
    assert out_sel.sum() < sel.sum() * 5


def test_scale_below_one_shrinks_selection():
    img = _make_layer(h=40, w=40)
    img[15:25, 15:25, :] = (200, 50, 50, 255)
    sel = _box_selection(img.shape[:2], 15, 25, 15, 25)
    _, out_sel = transform_selection(img, sel, scale=0.5)
    assert out_sel.sum() < sel.sum()


def test_anchor_overrides_default_centre():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 5, 10, 5, 10)
    # Rotate 180° around (0, 0); the (5..10, 5..10) box maps to
    # roughly (-10..-5, -10..-5) — entirely off-canvas.
    out_img, out_sel = transform_selection(
        img, sel, angle_deg=180.0, anchor=(0.0, 0.0),
    )
    assert out_img[..., 3].sum() == 0
    assert not out_sel.any()


def test_inputs_are_not_mutated():
    img = _make_layer()
    img[5:10, 5:10, :] = (255, 0, 0, 255)
    sel = _box_selection(img.shape[:2], 5, 10, 5, 10)
    img_snapshot = img.copy()
    sel_snapshot = sel.copy()
    transform_selection(img, sel, dx=3)
    np.testing.assert_array_equal(img, img_snapshot)
    np.testing.assert_array_equal(sel, sel_snapshot)


def test_rejects_zero_scale():
    img = _make_layer()
    sel = _box_selection(img.shape[:2], 0, 5, 0, 5)
    with pytest.raises(ValueError, match="scale"):
        transform_selection(img, sel, scale=0.0)


def test_rejects_negative_scale():
    img = _make_layer()
    sel = _box_selection(img.shape[:2], 0, 5, 0, 5)
    with pytest.raises(ValueError, match="scale"):
        transform_selection(img, sel, scale=-1.0)


def test_rejects_non_rgba_image():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    sel = _box_selection((10, 10), 0, 5, 0, 5)
    with pytest.raises(ValueError, match="HxWx4"):
        transform_selection(rgb, sel)


def test_rejects_mismatched_mask_shape():
    img = _make_layer()
    bad_sel = np.zeros((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError, match="does not match"):
        transform_selection(img, bad_sel)


def test_rejects_non_bool_mask():
    img = _make_layer()
    bad_sel = np.zeros((20, 20), dtype=np.uint8)
    with pytest.raises(ValueError, match="bool"):
        transform_selection(img, bad_sel)


# ---------------------------------------------------------------------------
# Document.transform_selection
# ---------------------------------------------------------------------------


@pytest.fixture
def document_with_box_selection():
    doc = PaintDocument()
    base = np.zeros((20, 20, 4), dtype=np.uint8)
    base[5:10, 5:10, :] = (200, 50, 50, 255)
    doc.load_image(base)
    sel = _box_selection((20, 20), 5, 10, 5, 10)
    doc.set_selection(sel)
    return doc


def test_document_transform_selection_translates(document_with_box_selection):
    doc = document_with_box_selection
    assert doc.transform_selection(dx=3) is True
    layer = doc.active_layer()
    assert layer.image[7, 5, 3] == 0   # original cleared
    assert tuple(layer.image[7, 8]) == (200, 50, 50, 255)


def test_document_transform_selection_no_selection_returns_false():
    doc = PaintDocument()
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    doc.load_image(base)
    assert doc.transform_selection(dx=5) is False


def test_document_transform_selection_empty_selection_returns_false():
    doc = PaintDocument()
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    doc.load_image(base)
    doc.set_selection(np.zeros((10, 10), dtype=np.bool_))
    assert doc.transform_selection(dx=5) is False


def test_document_transform_selection_notifies_listeners(document_with_box_selection):
    doc = document_with_box_selection
    calls = []
    doc.listen(lambda: calls.append(1))
    doc.transform_selection(dx=3)
    assert calls
