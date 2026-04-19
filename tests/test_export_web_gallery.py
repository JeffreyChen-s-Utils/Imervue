"""Tests for the web-gallery HTML generator helpers (no Qt required)."""
from __future__ import annotations

import pytest


@pytest.fixture
def wg():
    from Imervue.export import web_gallery as m
    return m


class TestTileHtml:
    def test_escapes_special_chars_in_caption(self, wg):
        html = wg._build_tile_html("t.jpg", "full.jpg", "<script>&")
        assert "&lt;script&gt;" in html
        assert "&amp;" in html

    def test_tile_contains_full_href(self, wg):
        html = wg._build_tile_html("t.jpg", "images/a.jpg", "a.jpg")
        assert 'data-full="images/a.jpg"' in html

    def test_tile_escapes_quotes_in_src(self, wg):
        html = wg._build_tile_html('t"x.jpg', "full.jpg", "x")
        # Double quote should be escaped inside attribute.
        assert "&quot;" in html or "\\\"" in html


class TestPlaceOriginal:
    def test_copy_originals_writes_into_images_dir(self, wg, tmp_path):
        src = tmp_path / "a.jpg"
        src.write_bytes(b"fake")
        out = tmp_path / "out"
        out.mkdir()
        href = wg._place_original(src, out, copy=True)
        assert href == "images/a.jpg"
        assert (out / "images" / "a.jpg").exists()

    def test_copy_disambiguates_collisions(self, wg, tmp_path):
        src_a = tmp_path / "dup.jpg"
        src_a.write_bytes(b"one")
        out = tmp_path / "out"
        out.mkdir()
        href1 = wg._place_original(src_a, out, copy=True)
        href2 = wg._place_original(src_a, out, copy=True)
        assert href1 != href2
        # Both files should exist on disk under the images/ subdir.
        assert (out / href1).exists()
        assert (out / href2).exists()

    def test_reference_mode_returns_uri(self, wg, tmp_path):
        src = tmp_path / "a.jpg"
        src.write_bytes(b"")
        href = wg._place_original(src, tmp_path / "out", copy=False)
        assert href.startswith("file:")
