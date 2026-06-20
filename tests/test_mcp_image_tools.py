"""Tests for the image-analysis MCP tool handlers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.tools import (
    _resize_dims,
    apply_frame,
    apply_watermark,
    build_collage,
    crop_image,
    find_similar,
    image_statistics,
    image_thumbnail,
    ocr_text,
    quality_metrics,
    read_histogram,
    resize_image,
)


def _save(path, value=128, h=24, w=24):
    Image.fromarray(np.full((h, w, 3), value, dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def _save_rgba(path, h=40, w=60):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = 30
    arr[..., 3] = 255
    Image.fromarray(arr, "RGBA").save(str(path))
    return str(path)


def _save_noisy(path, h=24, w=24):
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8), "RGB").save(str(path))
    return str(path)


def test_image_statistics_shape(tmp_path):
    result = image_statistics(_save(tmp_path / "a.png", value=100))
    assert result["path"].endswith("a.png")
    stats = result["statistics"]
    assert set(stats) == {"r", "g", "b", "luma"}
    assert stats["r"]["mean"] == 100.0  # NOSONAR - flat channel
    assert set(stats["r"]) == {"mean", "min", "max", "std", "median"}


def test_quality_metrics_keys(tmp_path):
    result = quality_metrics(_save_noisy(tmp_path / "n.png"))
    metrics = result["metrics"]
    assert set(metrics) == {
        "colorfulness", "entropy", "rms_contrast", "edge_density", "noise_sigma"}
    assert result["path"].endswith("n.png")


def test_missing_file_raises():
    with pytest.raises(ValueError):
        image_statistics("/no/such/file.png")
    with pytest.raises(ValueError):
        quality_metrics("/no/such/file.png")


def test_read_histogram_shape(tmp_path):
    result = read_histogram(_save(tmp_path / "h.png", value=100))
    hist = result["histogram"]
    assert set(hist) == {"r", "g", "b", "luma"}
    assert len(hist["r"]) == 256
    # A flat value-100 image puts every pixel in one bin.
    assert hist["r"][100] == 24 * 24
    assert "over_fraction" in result["clipping"]


def test_image_thumbnail_data_uri(tmp_path):
    result = image_thumbnail(_save(tmp_path / "t.png", h=400, w=600), max_size=64)
    assert result["data_uri"].startswith("data:image/png;base64,")
    assert max(result["width"], result["height"]) <= 64


def test_image_thumbnail_caps_max_size(tmp_path):
    result = image_thumbnail(_save(tmp_path / "t.png", h=2000, w=2000), max_size=99999)
    assert max(result["width"], result["height"]) <= 512


def test_ocr_text_degrades_gracefully(tmp_path):
    # Whether or not Tesseract is installed, the tool must return a dict.
    result = ocr_text(_save(tmp_path / "doc.png"))
    assert "available" in result and "text" in result
    assert isinstance(result["text"], str)


def test_find_similar_groups_duplicates(tmp_path):
    ramp = np.tile(np.linspace(0, 255, 32, dtype=np.uint8), (32, 1))
    Image.fromarray(ramp, "L").convert("RGB").save(str(tmp_path / "a.png"))
    Image.fromarray(ramp, "L").convert("RGB").save(str(tmp_path / "b.png"))
    Image.fromarray(ramp.T, "L").convert("RGB").save(str(tmp_path / "c.png"))
    result = find_similar(str(tmp_path), threshold=0)
    assert result["group_count"] == 1
    assert len(result["groups"][0]) == 2


def test_find_similar_missing_folder_raises():
    with pytest.raises(ValueError):
        find_similar("/no/such/folder")


def test_registered_in_default_tools():
    from Imervue.mcp_server.tools import _TOOL_DEFINITIONS
    names = {entry["name"] for entry in _TOOL_DEFINITIONS}
    assert {"image_statistics", "quality_metrics", "read_histogram",
            "ocr_text", "image_thumbnail", "find_similar",
            "apply_watermark", "apply_frame", "build_collage",
            "crop_image", "resize_image"} <= names


# ---------------------------------------------------------------------------
# resize_image
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("src_w,src_h,w,h,expected", [
    (100, 50, 200, 80, (200, 80)),      # exact, both given
    (100, 50, 50, None, (50, 25)),      # width only -> half scale
    (100, 50, None, 100, (200, 100)),   # height only -> double scale
    (3, 10, 1, None, (1, 3)),           # rounding stays >= 1
    (10, 3, None, 1, (3, 1)),
])
def test_resize_dims_preserves_aspect(src_w, src_h, w, h, expected):
    assert _resize_dims(src_w, src_h, w, h) == expected


def test_resize_image_exact(tmp_path):
    src = _save(tmp_path / "src.png", h=40, w=60)
    dst = tmp_path / "out.png"
    result = resize_image(src, str(dst), width=30, height=20)
    assert Image.open(dst).size == (30, 20)
    assert result["width"] == 30 and result["height"] == 20


def test_resize_image_width_only_keeps_aspect(tmp_path):
    src = _save(tmp_path / "src.png", h=40, w=80)
    dst = tmp_path / "out.png"
    result = resize_image(src, str(dst), width=40)
    assert result["width"] == 40
    assert result["height"] == 20  # 40 * (40/80)


def test_resize_image_requires_a_dimension(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="at least one"):
        resize_image(src, str(tmp_path / "out.png"))


def test_resize_image_non_positive_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="positive"):
        resize_image(src, str(tmp_path / "out.png"), width=0)


def test_resize_image_flattens_alpha_for_jpeg(tmp_path):
    src = _save_rgba(tmp_path / "src.png", h=40, w=40)
    dst = tmp_path / "out.jpg"
    resize_image(src, str(dst), width=20)
    assert Image.open(dst).mode == "RGB"


def test_resize_image_missing_source_raises(tmp_path):
    with pytest.raises(ValueError):
        resize_image("/no/such.png", str(tmp_path / "out.png"), width=10)


def test_resize_image_missing_destination_parent_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="destination parent"):
        resize_image(src, str(tmp_path / "nope" / "out.png"), width=10)


# ---------------------------------------------------------------------------
# crop_image
# ---------------------------------------------------------------------------


def test_crop_image_extracts_region(tmp_path):
    src = _save(tmp_path / "src.png", h=40, w=60)
    dst = tmp_path / "crop.png"
    result = crop_image(src, str(dst), x=10, y=5, width=20, height=15)
    assert dst.exists()
    assert result["width"] == 20
    assert result["height"] == 15
    out = Image.open(dst)
    assert out.size == (20, 15)


def test_crop_image_full_extent_allowed(tmp_path):
    src = _save(tmp_path / "src.png", h=30, w=30)
    dst = tmp_path / "crop.png"
    result = crop_image(src, str(dst), x=0, y=0, width=30, height=30)
    assert result["width"] == 30 and result["height"] == 30


def test_crop_image_box_exceeds_bounds_raises(tmp_path):
    src = _save(tmp_path / "src.png", h=20, w=20)
    with pytest.raises(ValueError, match="exceeds"):
        crop_image(src, str(tmp_path / "out.png"), x=10, y=10, width=20, height=5)


def test_crop_image_negative_origin_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="non-negative"):
        crop_image(src, str(tmp_path / "out.png"), x=-1, y=0, width=5, height=5)


def test_crop_image_non_positive_size_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="positive"):
        crop_image(src, str(tmp_path / "out.png"), x=0, y=0, width=0, height=5)


def test_crop_image_flattens_alpha_for_jpeg(tmp_path):
    src = _save_rgba(tmp_path / "src.png", h=40, w=40)
    dst = tmp_path / "out.jpg"
    crop_image(src, str(dst), x=2, y=2, width=10, height=10)
    assert Image.open(dst).mode == "RGB"


def test_crop_image_missing_source_raises(tmp_path):
    with pytest.raises(ValueError):
        crop_image("/no/such.png", str(tmp_path / "out.png"),
                   x=0, y=0, width=5, height=5)


def test_crop_image_missing_destination_parent_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="destination parent"):
        crop_image(src, str(tmp_path / "nope" / "out.png"),
                   x=0, y=0, width=5, height=5)


# ---------------------------------------------------------------------------
# build_collage
# ---------------------------------------------------------------------------


def test_build_collage_grid_dimensions(tmp_path):
    sources = [_save(tmp_path / f"i{n}.png", value=50 + n * 30) for n in range(3)]
    dst = tmp_path / "collage.png"
    result = build_collage(
        sources, str(dst), columns=2, cell_width=100, cell_height=80,
        gap=10, margin=5,
    )
    assert dst.exists()
    assert result["image_count"] == 3
    assert result["columns"] == 2
    # 3 images, 2 columns -> 2 rows. width = 2*5 + 2*100 + 1*10 = 220.
    assert result["width"] == 220
    # height = 2*5 + 2*80 + 1*10 = 180.
    assert result["height"] == 180


def test_build_collage_reserves_full_column_width(tmp_path):
    src = _save(tmp_path / "solo.png")
    dst = tmp_path / "one.png"
    result = build_collage([src], str(dst), columns=4, cell_width=60, cell_height=60,
                           gap=0, margin=0)
    # One image but 4 columns requested -> full 4-wide canvas, single row.
    assert result["columns"] == 4
    assert result["width"] == 240   # 4 * 60
    assert result["height"] == 60   # 1 row * 60


def test_build_collage_flattens_alpha_for_jpeg(tmp_path):
    src = _save_rgba(tmp_path / "a.png")
    dst = tmp_path / "out.jpg"
    build_collage([src], str(dst), cell_width=50, cell_height=50)
    assert Image.open(dst).mode == "RGB"


def test_build_collage_empty_sources_raises(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        build_collage([], str(tmp_path / "out.png"))


def test_build_collage_too_many_images_raises(tmp_path):
    src = _save(tmp_path / "a.png")
    with pytest.raises(ValueError, match="at most"):
        build_collage([src] * 201, str(tmp_path / "out.png"))


def test_build_collage_missing_source_raises(tmp_path):
    with pytest.raises(ValueError):
        build_collage(["/no/such.png"], str(tmp_path / "out.png"))


def test_build_collage_missing_destination_parent_raises(tmp_path):
    src = _save(tmp_path / "a.png")
    with pytest.raises(ValueError, match="destination parent"):
        build_collage([src], str(tmp_path / "nope" / "out.png"))


def test_build_collage_clamps_out_of_range_background(tmp_path):
    src = _save(tmp_path / "a.png")
    dst = tmp_path / "out.png"
    build_collage([src], str(dst), background=[999, -1, 100], cell_width=40,
                  cell_height=40)
    assert dst.exists()


# ---------------------------------------------------------------------------
# apply_watermark
# ---------------------------------------------------------------------------


def test_apply_watermark_writes_visible_mark(tmp_path):
    src = _save(tmp_path / "src.png", value=30, h=80, w=120)
    dst = tmp_path / "out.png"
    result = apply_watermark(src, str(dst), "© Imervue", corner="bottom-right")
    assert result["corner"] == "bottom-right"
    assert result["size_bytes"] > 0
    assert dst.exists()
    # The flat source had no bright pixels; the white text introduces some.
    out = np.asarray(Image.open(dst).convert("RGBA"))
    assert out.shape[:2] == (80, 120)
    assert out[..., :3].max() > 30


def test_apply_watermark_flattens_alpha_for_jpeg(tmp_path):
    src = _save_rgba(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    result = apply_watermark(src, str(dst), "mark")
    assert dst.exists()
    assert Image.open(dst).mode == "RGB"
    assert result["destination"].endswith("out.jpg")


def test_apply_watermark_clamps_out_of_range_color(tmp_path):
    src = _save(tmp_path / "src.png")
    dst = tmp_path / "out.png"
    # Out-of-range channels must be clamped, not crash.
    apply_watermark(src, str(dst), "x", color=[300, -5, 128])
    assert dst.exists()


def test_apply_watermark_empty_text_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="text"):
        apply_watermark(src, str(tmp_path / "out.png"), "   ")


def test_apply_watermark_invalid_corner_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="corner"):
        apply_watermark(src, str(tmp_path / "out.png"), "x", corner="middle")


def test_apply_watermark_invalid_color_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="color"):
        apply_watermark(src, str(tmp_path / "out.png"), "x", color=[255, 255])


def test_apply_watermark_missing_source_raises(tmp_path):
    with pytest.raises(ValueError):
        apply_watermark("/no/such.png", str(tmp_path / "out.png"), "x")


def test_apply_watermark_missing_destination_parent_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="destination parent"):
        apply_watermark(src, str(tmp_path / "nope" / "out.png"), "x")


# ---------------------------------------------------------------------------
# apply_frame
# ---------------------------------------------------------------------------


def test_apply_frame_grows_canvas_by_border(tmp_path):
    src = _save(tmp_path / "src.png", h=24, w=24)
    dst = tmp_path / "framed.png"
    result = apply_frame(src, str(dst), border=10)
    assert dst.exists()
    # 24 + 2*10 border on each axis.
    assert result["width"] == 44
    assert result["height"] == 44
    assert result["size_bytes"] > 0


def test_apply_frame_bottom_extra_adds_height_only(tmp_path):
    src = _save(tmp_path / "src.png", h=30, w=30)
    result = apply_frame(src, str(tmp_path / "out.png"), border=5, bottom_extra=20)
    assert result["width"] == 40            # 30 + 2*5
    assert result["height"] == 60           # 30 + 2*5 + 20


def test_apply_frame_with_caption(tmp_path):
    src = _save(tmp_path / "src.png", h=40, w=80)
    dst = tmp_path / "cap.png"
    result = apply_frame(
        src, str(dst), border=8, bottom_extra=30,
        caption="Hello", text_color=[10, 10, 10],
    )
    assert dst.exists()
    assert result["height"] == 40 + 16 + 30


def test_apply_frame_flattens_alpha_for_jpeg(tmp_path):
    src = _save_rgba(tmp_path / "src.png")
    dst = tmp_path / "out.jpg"
    apply_frame(src, str(dst), border=6)
    assert Image.open(dst).mode == "RGB"


def test_apply_frame_clamps_out_of_range_color(tmp_path):
    src = _save(tmp_path / "src.png")
    dst = tmp_path / "out.png"
    apply_frame(src, str(dst), color=[999, -10, 50])
    assert dst.exists()


def test_apply_frame_invalid_color_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="color"):
        apply_frame(src, str(tmp_path / "out.png"), text_color=[0, 0])


def test_apply_frame_missing_source_raises(tmp_path):
    with pytest.raises(ValueError):
        apply_frame("/no/such.png", str(tmp_path / "out.png"))


def test_apply_frame_missing_destination_parent_raises(tmp_path):
    src = _save(tmp_path / "src.png")
    with pytest.raises(ValueError, match="destination parent"):
        apply_frame(src, str(tmp_path / "nope" / "out.png"))
