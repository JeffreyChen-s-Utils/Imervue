"""Tests for the EXIF sidebar's video-metadata formatter (pure, no widget)."""
from __future__ import annotations

from Imervue.gui.exif_sidebar import ExifSidebar

_LANG = {
    "exif_resolution": "Resolution",
    "exif_duration": "Duration",
    "exif_fps": "Frame rate",
    "exif_codec": "Codec",
}


def test_format_video_meta_full():
    meta = {"width": 1920, "height": 1080, "duration_s": 12.5, "fps": 30.0, "codec": "h264"}
    joined = " ".join(ExifSidebar._format_video_meta(meta, _LANG))
    assert "1920 x 1080" in joined
    assert "12.50s" in joined
    assert "30.00 fps" in joined
    assert "h264" in joined


def test_format_video_meta_partial_skips_missing():
    meta = {"width": 0, "height": 0, "duration_s": 0.0, "fps": 0.0, "codec": ""}
    assert ExifSidebar._format_video_meta(meta, _LANG) == []


def test_format_video_meta_resolution_only():
    meta = {"width": 640, "height": 480, "duration_s": 0.0, "fps": 0.0, "codec": ""}
    lines = ExifSidebar._format_video_meta(meta, _LANG)
    assert len(lines) == 1
    assert "640 x 480" in lines[0]


_GEO_LANG = {"exif_coordinates": "GPS", "exif_location": "Location"}


def test_format_location_with_gps():
    lines = ExifSidebar._format_location((40.71, -74.01), _GEO_LANG)
    joined = " ".join(lines)
    assert "40.71000" in joined
    assert "New York, United States" in joined


def test_format_location_none_returns_empty():
    assert ExifSidebar._format_location(None, _GEO_LANG) == []


def test_format_location_is_clickable_map_link():
    joined = " ".join(ExifSidebar._format_location((48.85, 2.35), _GEO_LANG))
    assert 'href="imervue:open-map"' in joined
    assert "Paris, France" in joined
