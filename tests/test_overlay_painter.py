"""Tests for the pure helpers extracted into ``overlay_painter``.

These cover the text/geometry logic that used to live inline in
``GPUImageView``'s OSD / Debug-HUD / pixel-view methods. They are pure
Python (no Qt, no GL) so they run on headless CI without a context.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gpu_image_view.overlay_painter import (
    _rgba_to_pixmap,
    debug_hud_lines,
    favorites_set,
    format_exif_osd_lines,
    human_file_size,
    loupe_source_rect,
    osd_lines,
    place_hud_box,
    visible_pixel_bounds,
)


# ---------------------------------------------------------------
# human_file_size
# ---------------------------------------------------------------
def test_human_file_size_missing_path_returns_dash():
    assert human_file_size("does/not/exist____.png") == "—"


def test_human_file_size_kb(tmp_path):
    p = tmp_path / "small.bin"
    p.write_bytes(b"x" * 2048)
    assert human_file_size(str(p)) == "2.0 KB"


def test_human_file_size_mb(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"x" * (3 * 1024 * 1024))
    assert human_file_size(str(p)) == "3.00 MB"


def test_human_file_size_boundary_one_mb(tmp_path):
    """Exactly 1 MiB crosses into the MB branch."""
    p = tmp_path / "edge.bin"
    p.write_bytes(b"x" * (1024 * 1024))
    assert human_file_size(str(p)) == "1.00 MB"


# ---------------------------------------------------------------
# favorites_set
# ---------------------------------------------------------------
def test_favorites_set_passthrough_set():
    src = {"a", "b"}
    assert favorites_set(src) is src


def test_favorites_set_from_list():
    assert favorites_set(["a", "b", "a"]) == {"a", "b"}


def test_favorites_set_from_none_is_empty():
    assert favorites_set(None) == set()


def test_favorites_set_from_non_iterable_is_empty():
    assert favorites_set(42) == set()


# ---------------------------------------------------------------
# osd_lines
# ---------------------------------------------------------------
def test_osd_lines_shape_and_format(tmp_path):
    p = tmp_path / "photo.JPG"
    p.write_bytes(b"x" * 1500)
    lines = osd_lines(str(p), 1920, 1080)
    assert lines[0] == "photo.JPG"
    assert lines[1] == "1920 × 1080"
    assert lines[2].startswith("JPG")
    assert "KB" in lines[2]


def test_osd_lines_no_extension(tmp_path):
    p = tmp_path / "noext"
    p.write_bytes(b"x")
    lines = osd_lines(str(p), 10, 20)
    assert lines[2].startswith("—")


# ---------------------------------------------------------------
# debug_hud_lines
# ---------------------------------------------------------------
def _stats(**over):
    base = {
        "vram_usage": 512 * 1024 * 1024,
        "vram_limit": 1024 * 1024 * 1024,
        "tile_tex": 12,
        "tile_cache": 30,
        "prefetch": 5,
        "prefetch_workers": 2,
        "active_threads": 3,
        "max_threads": 8,
        "generation": 7,
        "zoom": 1.5,
    }
    base.update(over)
    return base


def test_debug_hud_lines_count_and_content():
    lines = debug_hud_lines(_stats())
    assert len(lines) == 5
    assert "512.0 /" in lines[0]
    assert "50.0%" in lines[0]
    assert "Tile tex" in lines[1]
    assert "Threads" in lines[3]
    assert "Zoom 150.0%" in lines[4]


def test_debug_hud_lines_zero_limit_no_zero_division():
    lines = debug_hud_lines(_stats(vram_limit=0, vram_usage=0))
    assert "0.0%" in lines[0]


# ---------------------------------------------------------------
# place_hud_box
# ---------------------------------------------------------------
def test_place_hud_box_default_to_right():
    hx, hy = place_hud_box(100, 100, 20, 80, 60, view_w=800, view_h=600)
    assert hx == 100 + 20 + 12
    assert hy == 100


def test_place_hud_box_flips_left_when_overflow_right():
    hx, _ = place_hud_box(780, 100, 20, 80, 60, view_w=800, view_h=600)
    assert hx == 780 - 80 - 12


def test_place_hud_box_clamps_bottom_overflow():
    _, hy = place_hud_box(100, 580, 20, 80, 60, view_w=800, view_h=600)
    assert hy == 600 - 60 - 4


def test_place_hud_box_never_negative_y():
    _, hy = place_hud_box(0, 0, 0, 80, 10000, view_w=800, view_h=600)
    assert hy == 0


# ---------------------------------------------------------------
# visible_pixel_bounds
# ---------------------------------------------------------------
def test_visible_pixel_bounds_clamped_to_image():
    x0, y0, x1, y1 = visible_pixel_bounds(
        zoom=1.0, off_x=0.0, off_y=0.0,
        view_w=100, view_h=100, img_w=50, img_h=40,
    )
    assert (x0, y0) == (0, 0)
    assert x1 == 50
    assert y1 == 40


def test_visible_pixel_bounds_with_pan_offset():
    # Panned so the top-left of the viewport sits at image pixel (10, 5).
    x0, y0, x1, y1 = visible_pixel_bounds(
        zoom=2.0, off_x=-20.0, off_y=-10.0,
        view_w=40, view_h=40, img_w=1000, img_h=1000,
    )
    assert (x0, y0) == (10, 5)
    assert x1 == pytest.approx(31, abs=1)
    assert y1 == pytest.approx(26, abs=1)


# ---------------------------------------------------------------
# _rgba_to_pixmap (filmstrip / loading-preview thumbnail handoff)
# ---------------------------------------------------------------
def test_rgba_to_pixmap_preserves_dimensions(qapp):
    arr = np.zeros((12, 20, 4), dtype=np.uint8)
    arr[..., 0] = 255  # opaque red
    arr[..., 3] = 255
    pixmap = _rgba_to_pixmap(arr)
    assert not pixmap.isNull()
    assert pixmap.width() == 20
    assert pixmap.height() == 12


def test_rgba_to_pixmap_accepts_non_contiguous(qapp):
    # A sliced (non-contiguous) view must still convert without raising.
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    base[..., 3] = 255
    view = base[::2, ::2]
    pixmap = _rgba_to_pixmap(view)
    assert pixmap.width() == 5
    assert pixmap.height() == 5


# ---------------------------------------------------------------
# loupe_source_rect
# ---------------------------------------------------------------
class TestLoupeSourceRect:
    def test_centred_crop_well_inside(self):
        assert loupe_source_rect(100, 100, 40, 40, 1000, 1000) == (80, 80, 120, 120)

    def test_clamps_at_left_edge(self):
        assert loupe_source_rect(5, 100, 40, 40, 1000, 1000) == (0, 80, 40, 120)

    def test_clamps_at_right_edge(self):
        assert loupe_source_rect(995, 100, 40, 40, 1000, 1000) == (960, 80, 1000, 120)

    def test_image_smaller_than_sample(self):
        assert loupe_source_rect(5, 5, 40, 40, 20, 20) == (0, 0, 20, 20)


# ---------------------------------------------------------------
# format_exif_osd_lines
# ---------------------------------------------------------------
class TestFormatExifOsdLines:
    def test_full_set(self):
        exif = {"ExposureTime": 0.005, "FNumber": 2.8,
                "ISOSpeedRatings": 400, "FocalLength": 50, "LensModel": "FE 50mm"}
        lines = format_exif_osd_lines(exif)
        assert lines[0] == "1/200s   f/2.8   ISO 400   50mm"
        assert lines[1] == "FE 50mm"

    def test_rational_tuples_are_handled(self):
        exif = {"ExposureTime": (1, 200), "FNumber": (28, 10)}
        assert format_exif_osd_lines(exif)[0] == "1/200s   f/2.8"

    def test_long_exposure_in_seconds(self):
        assert format_exif_osd_lines({"ExposureTime": 2.0})[0] == "2s"

    def test_iso_tuple_uses_first(self):
        assert format_exif_osd_lines({"ISOSpeedRatings": (800,)})[0] == "ISO 800"

    def test_partial_data_skips_missing_fields(self):
        assert format_exif_osd_lines({"ISOSpeedRatings": 100}) == ["ISO 100"]

    def test_malformed_values_are_dropped(self):
        exif = {"FNumber": "bad", "ExposureTime": None, "FocalLength": 0}
        assert format_exif_osd_lines(exif) == []

    def test_lens_only_is_stripped(self):
        assert format_exif_osd_lines({"LensModel": "  Canon EF  "}) == ["Canon EF"]

    def test_empty_returns_no_lines(self):
        assert format_exif_osd_lines({}) == []
