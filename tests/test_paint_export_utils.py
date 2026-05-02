"""Tests for export utilities — watermark, per-layer export, slice export."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.export_utils import (
    Slice,
    WATERMARK_POSITIONS,
    apply_watermark,
    export_layer,
    slice_export,
)


def _solid(rgb, h=40, w=40):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., :3] = rgb
    img[..., 3] = 255
    return img


def _watermark(h=8, w=8):
    wm = np.zeros((h, w, 4), dtype=np.uint8)
    wm[..., :3] = (200, 50, 50)
    wm[..., 3] = 255
    return wm


# ---------------------------------------------------------------------------
# Slice dataclass
# ---------------------------------------------------------------------------


def test_slice_construction():
    s = Slice(name="head", x=10, y=10, w=30, h=30)
    assert s.name == "head"
    assert s.w == 30


def test_slice_is_frozen():
    s = Slice(name="x", x=0, y=0, w=10, h=10)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.x = 5  # type: ignore[misc]


def test_slice_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        Slice(name="   ", x=0, y=0, w=10, h=10)


def test_slice_rejects_zero_size():
    with pytest.raises(ValueError, match="positive size"):
        Slice(name="x", x=0, y=0, w=0, h=10)


# ---------------------------------------------------------------------------
# apply_watermark
# ---------------------------------------------------------------------------


def test_watermark_positions_constant():
    assert set(WATERMARK_POSITIONS) == {
        "top-left", "top-right", "bottom-left", "bottom-right", "center",
    }


def test_watermark_paints_at_bottom_right():
    img = _solid((255, 255, 255), h=40, w=40)
    wm = _watermark(h=8, w=8)
    out = apply_watermark(img, wm, position="bottom-right", padding=4)
    # Bottom-right corner pixel of the watermark area → wm colour.
    assert tuple(out[31, 31, :3]) == (200, 50, 50)
    # Top-left untouched.
    assert tuple(out[0, 0, :3]) == (255, 255, 255)


def test_watermark_top_left_position():
    img = _solid((255, 255, 255))
    wm = _watermark()
    out = apply_watermark(img, wm, position="top-left", padding=2)
    assert tuple(out[2, 2, :3]) == (200, 50, 50)


def test_watermark_center_position():
    img = _solid((255, 255, 255), h=40, w=40)
    wm = _watermark(h=8, w=8)
    out = apply_watermark(img, wm, position="center")
    # Centre of canvas should be wm colour.
    assert tuple(out[20, 20, :3]) == (200, 50, 50)


def test_watermark_zero_opacity_returns_copy():
    img = _solid((255, 255, 255))
    wm = _watermark()
    out = apply_watermark(img, wm, opacity=0.0)
    np.testing.assert_array_equal(out, img)


def test_watermark_unknown_position_raises():
    img = _solid((255, 255, 255))
    wm = _watermark()
    with pytest.raises(ValueError, match="unknown watermark position"):
        apply_watermark(img, wm, position="diagonal")


def test_watermark_too_large_raises():
    img = _solid((20, 20, 20), h=10, w=10)
    wm = _watermark(h=20, w=20)
    with pytest.raises(ValueError, match="does not fit"):
        apply_watermark(img, wm)


def test_watermark_rejects_non_rgba_image():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    wm = _watermark(h=4, w=4)
    with pytest.raises(ValueError, match="HxWx4"):
        apply_watermark(rgb, wm)


def test_watermark_does_not_mutate_input():
    img = _solid((255, 255, 255))
    snapshot = img.copy()
    apply_watermark(img, _watermark())
    np.testing.assert_array_equal(img, snapshot)


# ---------------------------------------------------------------------------
# export_layer
# ---------------------------------------------------------------------------


def test_export_layer_writes_png(tmp_path):
    layer = _solid((10, 200, 30))
    path = tmp_path / "layer.png"
    export_layer(layer, path)
    assert path.exists()
    loaded = np.array(Image.open(path))
    np.testing.assert_array_equal(loaded[..., :3], layer[..., :3])


def test_export_layer_creates_parent_directory(tmp_path):
    layer = _solid((0, 0, 0))
    path = tmp_path / "deep" / "nested" / "out.png"
    export_layer(layer, path)
    assert path.exists()


def test_export_layer_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        export_layer(rgb, "ignored.png")


# ---------------------------------------------------------------------------
# slice_export
# ---------------------------------------------------------------------------


def test_slice_export_writes_one_file_per_slice(tmp_path):
    img = _solid((100, 100, 100), h=40, w=40)
    slices = [
        Slice(name="top", x=0, y=0, w=40, h=20),
        Slice(name="bottom", x=0, y=20, w=40, h=20),
    ]
    written = slice_export(img, slices, tmp_path)
    assert len(written) == 2
    for path in written:
        assert path.exists()


def test_slice_export_filenames_use_slice_names(tmp_path):
    img = _solid((100, 100, 100))
    slices = [Slice(name="head", x=0, y=0, w=20, h=20)]
    paths = slice_export(img, slices, tmp_path)
    assert paths[0].name == "head.png"


def test_slice_export_clips_to_canvas_edge(tmp_path):
    img = _solid((100, 100, 100), h=20, w=20)
    slices = [Slice(name="overshoot", x=10, y=10, w=100, h=100)]
    paths = slice_export(img, slices, tmp_path)
    assert paths[0].exists()
    loaded = np.array(Image.open(paths[0]))
    # Clipped to 10×10 region.
    assert loaded.shape[:2] == (10, 10)


def test_slice_export_skips_off_canvas_slices(tmp_path):
    img = _solid((100, 100, 100), h=20, w=20)
    slices = [
        Slice(name="off", x=100, y=100, w=10, h=10),
        Slice(name="visible", x=0, y=0, w=10, h=10),
    ]
    paths = slice_export(img, slices, tmp_path)
    names = [p.name for p in paths]
    assert "off.png" not in names
    assert "visible.png" in names


def test_slice_export_path_traversal_filename_safe(tmp_path):
    img = _solid((100, 100, 100))
    slices = [Slice(name="../escape", x=0, y=0, w=10, h=10)]
    paths = slice_export(img, slices, tmp_path)
    # The path-separator chars get sanitised; the file lands inside
    # tmp_path with a safe name.
    assert paths[0].parent == tmp_path
    assert ".." not in paths[0].name


def test_slice_export_jpeg_format_drops_alpha(tmp_path):
    img = _solid((100, 100, 100))
    slices = [Slice(name="head", x=0, y=0, w=10, h=10)]
    paths = slice_export(img, slices, tmp_path, file_format="JPEG")
    assert paths[0].suffix == ".jpg"
    loaded = Image.open(paths[0])
    assert loaded.mode == "RGB"   # no alpha


def test_slice_export_unknown_format_raises(tmp_path):
    img = _solid((100, 100, 100))
    slices = [Slice(name="head", x=0, y=0, w=10, h=10)]
    with pytest.raises(ValueError, match="file_format"):
        slice_export(img, slices, tmp_path, file_format="GIF")


def test_slice_export_empty_list_returns_empty(tmp_path):
    img = _solid((100, 100, 100))
    assert slice_export(img, [], tmp_path) == []


def test_slice_export_creates_output_directory(tmp_path):
    img = _solid((100, 100, 100))
    nested = tmp_path / "exports" / "v1"
    slices = [Slice(name="head", x=0, y=0, w=10, h=10)]
    paths = slice_export(img, slices, nested)
    assert paths[0].parent == nested
    assert nested.is_dir()
