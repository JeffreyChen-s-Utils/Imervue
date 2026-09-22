"""Tests for the OSD / Debug-HUD text helpers.

Pure string formatting (no Qt, no GL), so these run on headless CI.
"""
from __future__ import annotations


from Imervue.gpu_image_view.osd_text import (
    debug_hud_lines,
    favorites_set,
    format_exif_osd_lines,
    human_file_size,
    osd_lines,
)


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


def test_favorites_set_passthrough_set():
    src = {"a", "b"}
    assert favorites_set(src) is src


def test_favorites_set_from_list():
    assert favorites_set(["a", "b", "a"]) == {"a", "b"}


def test_favorites_set_from_none_is_empty():
    assert favorites_set(None) == set()


def test_favorites_set_from_non_iterable_is_empty():
    assert favorites_set(42) == set()


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
