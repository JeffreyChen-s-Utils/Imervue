"""Tests for the image-analysis MCP tool handlers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.tools import (
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
            "ocr_text", "image_thumbnail", "find_similar"} <= names
