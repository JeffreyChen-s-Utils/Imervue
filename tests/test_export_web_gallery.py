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


class TestReviewCommentsKey:
    """The localStorage key is derived from the gallery title — same
    derivation must produce the same key, so a reviewer reopening
    the page sees their previous comments."""

    def test_stable_for_same_title(self, wg):
        assert wg.review_comments_key("My Review") == wg.review_comments_key("My Review")

    def test_distinct_per_title(self, wg):
        a = wg.review_comments_key("Shoot A")
        b = wg.review_comments_key("Shoot B")
        assert a != b

    def test_key_only_uses_safe_characters(self, wg):
        """Keys end up as JSON-escaped strings in the inlined JS
        and as ``localStorage`` lookups — keep them
        non-quote-bearing alphanumeric / underscore."""
        key = wg.review_comments_key('a "b" \n / c & d')
        assert all(c.isalnum() or c == "_" for c in key)

    def test_empty_title_yields_default(self, wg):
        """A gallery with no explicit title still has a stable
        key — defensive fallback so the export button doesn't
        bind to an empty namespace."""
        key = wg.review_comments_key("")
        assert key   # non-empty string


class TestTileWithReviewKey:
    def test_tile_omits_review_textarea_by_default(self, wg):
        """Default mode (no review) → no textarea so existing
        galleries render exactly as before."""
        html = wg._build_tile_html("t.jpg", "full.jpg", "cap")
        assert "<textarea" not in html

    def test_tile_includes_review_textarea_when_keyed(self, wg):
        html = wg._build_tile_html(
            "t.jpg", "full.jpg", "cap", review_key="img-001",
        )
        assert "<textarea" in html
        assert 'data-key="img-001"' in html

    def test_tile_escapes_review_key(self, wg):
        """A filename with quote / angle-bracket characters mustn't
        let attacker-controlled JSON into the rendered attribute."""
        html = wg._build_tile_html(
            "t.jpg", "full.jpg", "cap", review_key='evil"<script>',
        )
        assert "<script>" not in html.split("</textarea>", maxsplit=1)[0]


class TestReviewScript:
    def test_script_inlines_key_as_json(self, wg):
        """The key arrives in JS via ``JSON.stringify`` so quotes /
        unicode survive — verify it's literally JSON-encoded."""
        script = wg._build_review_script("my_key")
        assert '"my_key"' in script

    def test_script_wires_localstorage(self, wg):
        """Smoke check: the generated script must mention the APIs
        it uses (localStorage, an input listener, the export
        Blob path)."""
        script = wg._build_review_script("k")
        assert "localStorage" in script
        assert "addEventListener" in script
        assert "Blob" in script


class TestGenerateWebGalleryReviewMode:
    """End-to-end: drive the public generator and inspect the
    rendered index.html for the review additions."""

    def _stub_thumbnail(self, monkeypatch, wg):
        """The real ``_make_thumbnail`` needs a working QImage / Qt
        platform — stub it so the test runs in any env (incl. CI)."""
        def _fake(src, dest, _max_side, _quality):
            from pathlib import Path
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"fake-thumb")
            return True

        monkeypatch.setattr(wg, "_make_thumbnail", _fake)

    def test_default_gallery_has_no_review_bar(self, wg, monkeypatch, tmp_path):
        """Default mode keeps the CSS for #review-bar (stylesheet
        is shared) but must not emit the actual element / script."""
        self._stub_thumbnail(monkeypatch, wg)
        src = tmp_path / "a.jpg"
        src.write_bytes(b"")
        out = tmp_path / "gallery"
        wg.generate_web_gallery([str(src)], out)
        html = (out / "index.html").read_text(encoding="utf-8")
        assert '<div id="review-bar">' not in html
        assert "<textarea" not in html
        assert "export-comments" not in html

    def test_review_mode_emits_bar_and_textareas(
        self, wg, monkeypatch, tmp_path,
    ):
        self._stub_thumbnail(monkeypatch, wg)
        src = tmp_path / "a.jpg"
        src.write_bytes(b"")
        out = tmp_path / "gallery"
        wg.generate_web_gallery(
            [str(src)], out,
            wg.WebGalleryOptions(review_mode=True, title="Review Pass"),
        )
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "review-bar" in html
        assert "<textarea" in html
        assert "export-comments" in html

    def test_review_mode_uses_image_basename_as_key(
        self, wg, monkeypatch, tmp_path,
    ):
        """Per-image key is the source basename so renaming the
        output folder doesn't invalidate the reviewer's progress."""
        self._stub_thumbnail(monkeypatch, wg)
        src = tmp_path / "kitten.jpg"
        src.write_bytes(b"")
        out = tmp_path / "gallery"
        wg.generate_web_gallery(
            [str(src)], out, wg.WebGalleryOptions(review_mode=True),
        )
        html = (out / "index.html").read_text(encoding="utf-8")
        assert 'data-key="kitten.jpg"' in html

    def test_review_mode_inlines_localstorage_key(
        self, wg, monkeypatch, tmp_path,
    ):
        """The HTML page is self-contained — the script must
        reference the same key ``review_comments_key`` would
        produce so reloads round-trip."""
        self._stub_thumbnail(monkeypatch, wg)
        src = tmp_path / "a.jpg"
        src.write_bytes(b"")
        out = tmp_path / "gallery"
        wg.generate_web_gallery(
            [str(src)], out,
            wg.WebGalleryOptions(review_mode=True, title="Run 7"),
        )
        html = (out / "index.html").read_text(encoding="utf-8")
        expected_key = wg.review_comments_key("Run 7")
        assert expected_key in html
