"""Tests for the pure helpers extracted into ``overlay_painter``.

These cover the text/geometry logic that used to live inline in
``GPUImageView``'s OSD / Debug-HUD / pixel-view methods. They are pure
Python (no Qt, no GL) so they run on headless CI without a context.
"""
from __future__ import annotations

import pytest

from Imervue.gpu_image_view.overlay_painter import (
    debug_hud_lines,
    favorites_set,
    human_file_size,
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
