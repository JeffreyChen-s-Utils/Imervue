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


# ---------------------------------------------------------------------------
# Values from the file are shown as text, never interpreted as HTML
# ---------------------------------------------------------------------------

_HOSTILE = "<img src='C:/x.png'><b>Canon</b> & Co"
_ESCAPED = "&lt;img src=&#x27;C:/x.png&#x27;&gt;&lt;b&gt;Canon&lt;/b&gt; &amp; Co"


def test_exif_values_are_escaped(monkeypatch, tmp_path):
    from Imervue.gui import exif_sidebar
    monkeypatch.setattr(exif_sidebar, "get_exif_data", lambda _p: {
        "Make": _HOSTILE, "ExifImageWidth": "<i>9</i>", "ExifImageHeight": 4})
    joined = "".join(ExifSidebar._exif_lines(tmp_path / "a.jpg", {}))
    assert _ESCAPED in joined
    assert "<img" not in joined
    assert "&lt;i&gt;9&lt;/i&gt; x 4" in joined


def test_video_codec_is_escaped():
    joined = "".join(ExifSidebar._format_video_meta({"codec": _HOSTILE}, _LANG))
    assert _ESCAPED in joined
    assert "<img" not in joined


def test_place_name_is_escaped_inside_the_map_link(monkeypatch):
    from Imervue.image import reverse_geocode
    monkeypatch.setattr(reverse_geocode, "reverse_geocode", lambda _lat, _lon: _HOSTILE)
    lines = ExifSidebar._format_location((1.0, 2.0), {})
    assert _ESCAPED in lines[-1]
    assert lines[-1].count("<a ") == 1


def test_file_name_is_escaped(qapp, monkeypatch, tmp_path):
    from types import SimpleNamespace

    from Imervue.gui import exif_sidebar
    monkeypatch.setattr(exif_sidebar, "get_exif_data", lambda _p: {})
    shown: list[str] = []
    fake = SimpleNamespace(
        _collapsed=False, _load_note_for=lambda _p: None,
        _rating_widget=SimpleNamespace(bind_path=lambda _p: None),
        _info_label=SimpleNamespace(setText=shown.append),
        _video_lines=ExifSidebar._video_lines, _exif_lines=ExifSidebar._exif_lines,
        _file_stat_lines=ExifSidebar._file_stat_lines,
        _location_lines=lambda _p, _lang: [],
    )
    ExifSidebar.update_info(fake, str(tmp_path / "x<b>&y.jpg"))
    assert "x&lt;b&gt;&amp;y.jpg" in shown[0]
