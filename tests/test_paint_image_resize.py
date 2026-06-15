"""Tests for the image-resize helpers + Image Size dialog commit."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.image_menu import commit_image_resize
from Imervue.paint.image_resize import (
    DEFAULT_RESAMPLE,
    RESAMPLE_FILTERS,
    RESIZE_DIM_MAX,
    resize_mask,
    resize_rgba,
    resize_selection,
    scaled_dims_keep_aspect,
)
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _rgba(h: int, w: int) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[h // 2, w // 2, 0] = 200
    return arr


# ---------------------------------------------------------------------------
# resize_rgba
# ---------------------------------------------------------------------------


def test_resize_rgba_changes_shape():
    arr = _rgba(8, 16)
    out = resize_rgba(arr, new_w=4, new_h=2)
    assert out.shape == (2, 4, 4)
    assert out.dtype == np.uint8


def test_resize_rgba_returns_contiguous_buffer():
    arr = _rgba(8, 8)
    out = resize_rgba(arr, new_w=4, new_h=4)
    assert out.flags["C_CONTIGUOUS"]


def test_resize_rgba_identity_returns_copy_not_view():
    arr = _rgba(4, 4)
    out = resize_rgba(arr, new_w=4, new_h=4)
    # Same content, but a copy (not aliased).
    np.testing.assert_array_equal(out, arr)
    out[0, 0, 0] = 99
    assert int(arr[0, 0, 0]) != 99


def test_resize_rgba_does_not_mutate_input():
    arr = _rgba(8, 8)
    snapshot = arr.copy()
    resize_rgba(arr, new_w=4, new_h=4)
    np.testing.assert_array_equal(arr, snapshot)


def test_resize_rgba_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        resize_rgba(bad, new_w=2, new_h=2)


def test_resize_rgba_rejects_unknown_resample():
    arr = _rgba(4, 4)
    with pytest.raises(ValueError):
        resize_rgba(arr, new_w=2, new_h=2, resample="cubic")


def test_resize_rgba_clamps_dim_at_max():
    arr = _rgba(4, 4)
    with pytest.raises(ValueError):
        resize_rgba(arr, new_w=RESIZE_DIM_MAX + 1, new_h=4)


def test_resize_rgba_rejects_zero_dim():
    arr = _rgba(4, 4)
    with pytest.raises(ValueError):
        resize_rgba(arr, new_w=0, new_h=4)


@pytest.mark.parametrize("resample", RESAMPLE_FILTERS)
def test_resize_rgba_supports_every_documented_filter(resample):
    arr = _rgba(8, 8)
    out = resize_rgba(arr, new_w=4, new_h=4, resample=resample)
    assert out.shape == (4, 4, 4)


# ---------------------------------------------------------------------------
# resize_mask
# ---------------------------------------------------------------------------


def test_resize_mask_resizes_uint8():
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 2:6] = 200
    out = resize_mask(mask, new_w=4, new_h=4)
    assert out.shape == (4, 4)
    assert out.dtype == np.uint8


def test_resize_mask_rejects_non_2d():
    bad = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        resize_mask(bad, new_w=2, new_h=2)


def test_resize_mask_identity_returns_copy():
    mask = np.full((4, 4), 128, dtype=np.uint8)
    out = resize_mask(mask, new_w=4, new_h=4)
    np.testing.assert_array_equal(out, mask)
    out[0, 0] = 0
    assert int(mask[0, 0]) == 128


# ---------------------------------------------------------------------------
# resize_selection
# ---------------------------------------------------------------------------


def test_resize_selection_returns_bool():
    sel = np.zeros((8, 8), dtype=np.bool_)
    sel[2:6, 2:6] = True
    out = resize_selection(sel, new_w=4, new_h=4)
    assert out.shape == (4, 4)
    assert out.dtype == np.bool_


def test_resize_selection_uses_nearest_neighbour_thresholding():
    """Resampling a bool selection must produce a bool selection
    after re-thresholding — half-coverage pixels round one way."""
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[1:3, 1:3] = True
    out = resize_selection(sel, new_w=8, new_h=8)
    assert out.dtype == np.bool_
    # The centre of the upscaled selection must remain True.
    assert bool(out[3, 3])


def test_resize_selection_rejects_non_bool():
    with pytest.raises(ValueError):
        resize_selection(np.zeros((4, 4), dtype=np.uint8), new_w=2, new_h=2)


# ---------------------------------------------------------------------------
# scaled_dims_keep_aspect
# ---------------------------------------------------------------------------


def test_scaled_dims_landscape_limited_by_width():
    out = scaled_dims_keep_aspect(800, 600, target_w=400, target_h=400)
    assert out == (400, 300)


def test_scaled_dims_portrait_limited_by_height():
    out = scaled_dims_keep_aspect(300, 600, target_w=400, target_h=200)
    assert out == (100, 200)


def test_scaled_dims_square_unchanged():
    out = scaled_dims_keep_aspect(400, 400, target_w=200, target_h=200)
    assert out == (200, 200)


def test_scaled_dims_rejects_zero_input():
    with pytest.raises(ValueError):
        scaled_dims_keep_aspect(0, 100, target_w=50, target_h=50)


# ---------------------------------------------------------------------------
# PaintDocument.resize
# ---------------------------------------------------------------------------


def test_document_resize_changes_every_layer(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.add_layer()  # second layer
        ok = document.resize(64, 32)
        assert ok is True
        for i in range(document.layer_count):
            assert document.layer_at(i).image.shape == (32, 64, 4)
    finally:
        ws.deleteLater()


def test_document_resize_handles_layer_mask(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.add_layer_mask(fill=128)
        document.resize(20, 30)
        layer = document.active_layer()
        assert layer.mask is not None
        assert layer.mask.shape == (30, 20)
    finally:
        ws.deleteLater()


def test_document_resize_handles_active_selection(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        h, w = document.shape
        sel = np.zeros((h, w), dtype=np.bool_)
        sel[: h // 2, : w // 2] = True
        document.set_selection(sel)
        document.resize(40, 40)
        assert document.selection().shape == (40, 40)
    finally:
        ws.deleteLater()


def test_document_resize_empty_returns_false():
    from Imervue.paint.document import PaintDocument
    doc = PaintDocument()
    assert doc.resize(10, 10) is False


# ---------------------------------------------------------------------------
# Image-menu commit_image_resize
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_commit_resize_succeeds_with_valid_params(workspace):
    document = workspace.canvas().document()
    h_before, w_before = document.shape
    ok = commit_image_resize(workspace, {
        "width": w_before // 2 if w_before > 1 else 2,
        "height": h_before // 2 if h_before > 1 else 2,
        "resample": DEFAULT_RESAMPLE,
    })
    assert ok is True


def test_commit_resize_rejects_zero_dim(workspace):
    before = workspace.canvas().document().shape
    ok = commit_image_resize(workspace, {
        "width": 0, "height": 100, "resample": DEFAULT_RESAMPLE,
    })
    assert ok is False
    assert workspace.canvas().document().shape == before


def test_commit_resize_rejects_garbage_params(workspace):
    ok = commit_image_resize(workspace, {
        "width": "not a number", "height": 100,
    })
    assert ok is False


def test_commit_resize_unknown_resample_returns_false(workspace):
    ok = commit_image_resize(workspace, {
        "width": 50, "height": 50, "resample": "voodoo",
    })
    assert ok is False


def test_commit_resize_invalidates_composite(workspace):
    document = workspace.canvas().document()
    document.composite()
    assert document._composite_cache is not None  # noqa: SLF001
    commit_image_resize(workspace, {
        "width": 50, "height": 50, "resample": DEFAULT_RESAMPLE,
    })
    assert document._composite_cache is None  # noqa: SLF001
