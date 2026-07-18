"""Tests for the AI Object Remove plugin (mask selection + inpaint wiring)."""
from __future__ import annotations

import numpy as np
import pytest

from ai_object_remove.object_removal import (
    build_mask,
    classify_onnx_inputs,
    composite_inpaint,
    flood_fill_mask,
    grow_mask,
    image_coord_from_click,
    mask_to_nchw,
    onnx_inpaint,
    remove_object,
    to_nchw,
)


def _rgba(h, w, fill=(0, 0, 0)):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = fill
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# flood_fill_mask
# ---------------------------------------------------------------------------


def test_flood_fill_selects_solid_region():
    arr = _rgba(20, 20)
    arr[2:6, 2:6, 0] = 200  # a 4x4 red square
    mask = flood_fill_mask(arr, seed_x=3, seed_y=3, tolerance=10)
    assert mask[3, 3]
    assert int(mask.sum()) == 16


def test_flood_fill_stays_within_connected_region():
    arr = _rgba(20, 20)
    arr[2:6, 2:6, 0] = 200
    arr[14:18, 14:18, 0] = 200  # a second, disconnected square
    mask = flood_fill_mask(arr, seed_x=3, seed_y=3, tolerance=10)
    assert int(mask.sum()) == 16
    assert not mask[15, 15]


def test_flood_fill_tolerance_expands_selection():
    arr = _rgba(10, 10)
    arr[..., 0] = np.arange(10, dtype=np.uint8)[None, :] * 5  # horizontal ramp
    tight = flood_fill_mask(arr, 0, 0, tolerance=2)
    loose = flood_fill_mask(arr, 0, 0, tolerance=50)
    assert int(loose.sum()) > int(tight.sum())


def test_flood_fill_clamps_out_of_range_seed():
    arr = _rgba(8, 8)
    mask = flood_fill_mask(arr, seed_x=999, seed_y=-5, tolerance=5)
    assert mask.shape == (8, 8)
    assert mask.any()


def test_flood_fill_rejects_non_image():
    with pytest.raises(ValueError):
        flood_fill_mask(np.zeros((4, 4), dtype=np.uint8), 0, 0, 5)


# ---------------------------------------------------------------------------
# grow_mask / build_mask
# ---------------------------------------------------------------------------


def test_grow_mask_single_pixel_becomes_plus():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    grown = grow_mask(mask, 1)
    assert int(grown.sum()) == 5


def test_grow_mask_zero_radius_is_noop():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    assert int(grow_mask(mask, 0).sum()) == 1


def test_build_mask_grows_flood_region():
    arr = _rgba(20, 20)
    arr[8:12, 8:12, 0] = 200
    base = build_mask(arr, 9, 9, tolerance=10, grow=0)
    grown = build_mask(arr, 9, 9, tolerance=10, grow=2)
    assert int(grown.sum()) > int(base.sum())


# ---------------------------------------------------------------------------
# remove_object
# ---------------------------------------------------------------------------


def test_remove_object_fills_masked_region():
    arr = _rgba(8, 8, fill=(100, 100, 100))
    arr[3:5, 3:5, :3] = 0  # a dark hole to remove
    mask = np.zeros((8, 8), dtype=bool)
    mask[3:5, 3:5] = True
    out = remove_object(arr, mask, iterations=120)
    # The hole relaxes toward the surrounding mid-grey.
    assert out[3:5, 3:5, :3].mean() > 50
    # Untouched pixels are unchanged.
    assert out[0, 0, 0] == 100


def test_remove_object_empty_mask_is_noop():
    arr = _rgba(8, 8, fill=(100, 100, 100))
    mask = np.zeros((8, 8), dtype=bool)
    assert np.array_equal(remove_object(arr, mask), arr)


# ---------------------------------------------------------------------------
# image_coord_from_click
# ---------------------------------------------------------------------------


def test_click_centre_maps_to_image_centre():
    assert image_coord_from_click(240, 180, 480, 360, 240, 180) == (120, 90)


def test_click_in_letterbox_returns_none():
    # Tall image in a wide label leaves left/right margins.
    assert image_coord_from_click(10, 180, 480, 360, 100, 200) is None


def test_click_maps_with_letterbox_offset():
    assert image_coord_from_click(240, 180, 480, 360, 100, 200) == (50, 100)


def test_click_zero_size_returns_none():
    assert image_coord_from_click(10, 10, 480, 360, 0, 0) is None


# ---------------------------------------------------------------------------
# Qt smoke test
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ONNX inpaint helpers (pure pre/post + runtime guard)
# ---------------------------------------------------------------------------


def test_classify_image_and_mask_inputs():
    specs = [("image", [1, 3, 256, 256]), ("mask", [1, 1, 256, 256])]
    assert classify_onnx_inputs(specs) == ("image", "mask")


def test_classify_image_only():
    assert classify_onnx_inputs([("input", [1, 3, 512, 512])]) == ("input", None)


def test_classify_order_independent():
    specs = [("m", [1, 1, 64, 64]), ("img", [1, 3, 64, 64])]
    assert classify_onnx_inputs(specs) == ("img", "m")


def test_classify_unknown_shape_falls_back_to_first():
    assert classify_onnx_inputs([("x", ["N", "C", "H", "W"])]) == ("x", None)


def test_to_nchw_shape_and_dtype():
    out = to_nchw(np.zeros((4, 5, 3), dtype=np.float32))
    assert out.shape == (1, 3, 4, 5)
    assert out.dtype == np.float32


def test_mask_to_nchw():
    mask = np.zeros((4, 5), dtype=bool)
    mask[1, 1] = True
    out = mask_to_nchw(mask)
    assert out.shape == (1, 1, 4, 5)
    assert out[0, 0, 1, 1] == 1.0  # NOSONAR - exact array value
    assert out.dtype == np.float32


def test_composite_inpaint_replaces_only_masked():
    original = _rgba(4, 4, fill=(10, 20, 30))
    model_rgb = np.full((4, 4, 3), 200, dtype=np.uint8)
    mask = np.zeros((4, 4), dtype=bool)
    mask[1, 1] = True
    out = composite_inpaint(original, model_rgb, mask)
    assert tuple(out[1, 1, :3]) == (200, 200, 200)
    assert tuple(out[0, 0, :3]) == (10, 20, 30)
    assert out[0, 0, 3] == 255


def test_onnx_inpaint_missing_runtime_raises(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    mask = np.zeros((8, 8), dtype=bool)
    mask[2, 2] = True
    with pytest.raises(ImportError):
        onnx_inpaint(_rgba(8, 8), mask, "missing_model.onnx")


def test_dialog_smoke(qapp, tmp_path):
    from PIL import Image as PILImage

    from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog

    arr = _rgba(40, 40)
    arr[10:30, 10:30, 0] = 200  # an object to click
    path = tmp_path / "scene.png"
    PILImage.fromarray(arr, "RGBA").save(str(path))

    dialog = ObjectRemoveDialog(object(), str(path))
    try:
        dialog._on_click(dialog._preview.width() / 2, dialog._preview.height() / 2)
        # The flood-fill now runs on a worker thread; wait for it, then pump the
        # queued ready signal so the mask lands back on the GUI thread.
        if dialog._mask_worker is not None:
            dialog._mask_worker.wait(2000)
        for _ in range(20):
            qapp.processEvents()
            if dialog._mask is not None:
                break
        assert dialog._mask is not None
        assert dialog._mask.any()
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Flood-fill mask build moved off the GUI thread
# ---------------------------------------------------------------------------


class TestMaskWorker:
    def test_worker_computes_same_mask_as_build_mask(self, qapp):
        from ai_object_remove.ai_object_remove_plugin import _MaskWorker
        arr = np.zeros((8, 8, 4), dtype=np.uint8)
        arr[..., 3] = 255
        arr[2:5, 2:5, :3] = 200          # a distinct connected region
        worker = _MaskWorker(arr, 3, 3, 30, 0)
        results: list = []
        worker.ready.connect(lambda m: results.append(m))
        worker.run()                     # synchronous — no thread started

        assert len(results) == 1
        assert np.array_equal(results[0], build_mask(arr, 3, 3, 30, 0))

    def test_recompute_marks_dirty_while_worker_busy(self):
        from types import SimpleNamespace

        from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
        ws = SimpleNamespace(_seed=(1, 1), _mask_worker=object(), _mask_dirty=False)
        ObjectRemoveDialog._recompute_mask(ws)
        assert ws._mask_dirty is True    # queued to re-run; no second worker

    def test_recompute_noop_without_seed(self):
        from types import SimpleNamespace

        from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
        ws = SimpleNamespace(_seed=None, _mask_worker=None, _mask_dirty=False)
        ObjectRemoveDialog._recompute_mask(ws)
        assert ws._mask_dirty is False

    def test_on_mask_ready_reruns_when_dirty(self):
        from types import SimpleNamespace

        from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
        recompute, rendered = [], []
        ws = SimpleNamespace(
            _mask_worker=SimpleNamespace(wait=lambda: None),
            _mask_dirty=True,
            _seed=(2, 2),
            _render_preview=lambda: rendered.append(True),
            _recompute_mask=lambda: recompute.append(True),
        )
        sentinel = object()
        ObjectRemoveDialog._on_mask_ready(ws, sentinel)
        assert ws._mask is sentinel
        assert ws._mask_worker is None
        assert rendered == [True]
        assert recompute == [True]        # re-ran with the latest params

    def test_on_mask_ready_no_rerun_when_clean(self):
        from types import SimpleNamespace

        from ai_object_remove.ai_object_remove_plugin import ObjectRemoveDialog
        recompute = []
        ws = SimpleNamespace(
            _mask_worker=SimpleNamespace(wait=lambda: None),
            _mask_dirty=False,
            _seed=(2, 2),
            _render_preview=lambda: None,
            _recompute_mask=lambda: recompute.append(True),
        )
        ObjectRemoveDialog._on_mask_ready(ws, object())
        assert recompute == []
