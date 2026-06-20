"""Tests for the image-analysis MCP tool handlers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.tools import (
    apply_frame,
    apply_watermark,
    find_similar,
    image_statistics,
    image_thumbnail,
    ocr_text,
    quality_metrics,
    read_histogram,
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
            "apply_watermark", "apply_frame"} <= names


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
