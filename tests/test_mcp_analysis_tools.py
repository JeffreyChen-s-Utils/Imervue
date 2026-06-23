"""Functional tests for the read-only MCP analysis tools.

Covers extract_gps, dominant_colors and error_level_analysis handlers directly
(schema/structured-content parity lives in test_mcp_tool_schemas.py).
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.mcp_server.tools import (
    dominant_colors,
    error_level_analysis,
    extract_gps,
    search_images,
)


def _solid_png(tmp_path, name, rgb, size=(16, 16)):
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[...] = rgb
    path = tmp_path / name
    Image.fromarray(arr).save(path, format="PNG")
    return str(path)


def _two_tone_png(tmp_path, name, top_rgb, bottom_rgb):
    arr = np.zeros((20, 10, 3), dtype=np.uint8)
    arr[:15] = top_rgb   # 150 px of top colour
    arr[15:] = bottom_rgb  # 50 px of bottom colour
    path = tmp_path / name
    Image.fromarray(arr).save(path, format="PNG")
    return str(path)


# ---------------------------------------------------------------------------
# extract_gps
# ---------------------------------------------------------------------------


def test_extract_gps_absent_returns_nulls(tmp_path):
    path = _solid_png(tmp_path, "plain.png", (10, 20, 30))
    result = extract_gps(path)
    assert result["has_gps"] is False
    assert result["latitude"] is None
    assert result["longitude"] is None
    assert result["path"] == path


def test_extract_gps_present_returns_coords(tmp_path, monkeypatch):
    path = _solid_png(tmp_path, "geo.png", (10, 20, 30))
    monkeypatch.setattr("Imervue.image.gps.extract_gps", lambda _p: (35.68, 139.69))
    result = extract_gps(path)
    assert result["has_gps"] is True
    assert result["latitude"] == pytest.approx(35.68)
    assert result["longitude"] == pytest.approx(139.69)


def test_extract_gps_missing_file_raises(tmp_path):
    with pytest.raises((FileNotFoundError, ValueError)):
        extract_gps(str(tmp_path / "nope.png"))


# ---------------------------------------------------------------------------
# dominant_colors
# ---------------------------------------------------------------------------


def test_dominant_colors_solid_image_exact(tmp_path):
    path = _solid_png(tmp_path, "orange.png", (200, 120, 0))
    result = dominant_colors(path, n_colors=4)
    assert result["color_count"] == len(result["colors"])
    first = result["colors"][0]
    assert first["rgb"] == [200, 120, 0]
    assert first["hex"] == "#c87800"
    assert first["pixel_count"] > 0


def test_dominant_colors_sorted_and_hex_matches_rgb(tmp_path):
    # median-cut averages within buckets, so assert ordering + hex/rgb
    # consistency rather than exact bucket colours.
    path = _two_tone_png(tmp_path, "two.png", (200, 120, 0), (0, 0, 0))
    colors = dominant_colors(path, n_colors=4)["colors"]
    counts = [c["pixel_count"] for c in colors]
    assert counts == sorted(counts, reverse=True)
    for c in colors:
        r, g, b = c["rgb"]
        assert c["hex"] == f"#{r:02x}{g:02x}{b:02x}"


def test_dominant_colors_clamps_out_of_range_counts(tmp_path):
    path = _solid_png(tmp_path, "solid.png", (50, 60, 70))
    # Absurd / zero counts must not raise — they clamp to the palette range.
    big = dominant_colors(path, n_colors=100000)
    assert big["color_count"] >= 1
    small = dominant_colors(path, n_colors=0)
    assert small["color_count"] >= 1


# ---------------------------------------------------------------------------
# error_level_analysis
# ---------------------------------------------------------------------------


def test_error_level_analysis_returns_png_data_uri(tmp_path):
    path = _solid_png(tmp_path, "ela.png", (120, 130, 140), size=(24, 18))
    result = error_level_analysis(path)
    assert result["width"] == 24
    assert result["height"] == 18
    assert result["data_uri"].startswith("data:image/png;base64,")


def test_error_level_analysis_clamps_quality(tmp_path):
    path = _solid_png(tmp_path, "ela2.png", (90, 90, 90))
    # Out-of-range quality is clamped inside the analyser, not raised.
    result = error_level_analysis(path, quality=9000, scale=1)
    assert result["data_uri"].startswith("data:image/png;base64,")


# ---------------------------------------------------------------------------
# search_images
# ---------------------------------------------------------------------------


def _png(tmp_path, name, size=(16, 16)):
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    path = tmp_path / name
    Image.fromarray(arr).save(path, format="PNG")
    return path


def test_search_images_by_extension(tmp_path):
    _png(tmp_path, "a.png")
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(
        tmp_path / "b.jpg", format="JPEG")
    result = search_images(str(tmp_path), "ext:png")
    assert result["count"] == 1
    assert result["matches"][0].endswith("a.png")


def test_search_images_by_name_and_dimension(tmp_path):
    _png(tmp_path, "sunset_wide.png", size=(120, 20))
    _png(tmp_path, "narrow.png", size=(20, 20))
    by_name = search_images(str(tmp_path), "name:sunset")
    assert [m.split("\\")[-1].split("/")[-1] for m in by_name["matches"]] == [
        "sunset_wide.png"]
    by_dim = search_images(str(tmp_path), "width:>100")
    assert by_dim["count"] == 1


@pytest.mark.parametrize("query", ["rating:>=3", "tag:trip"])
def test_search_images_rejects_stateful_fields(tmp_path, query):
    _png(tmp_path, "x.png")
    with pytest.raises(ValueError, match="unavailable in the standalone server"):
        search_images(str(tmp_path), query)


def test_search_images_missing_folder_raises(tmp_path):
    with pytest.raises((FileNotFoundError, ValueError, NotADirectoryError)):
        search_images(str(tmp_path / "nope"), "ext:png")
