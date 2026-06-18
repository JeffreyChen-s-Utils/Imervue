"""Tests for batch location → XMP keyword tagging."""
from __future__ import annotations

import pytest

pytest.importorskip("defusedxml")

from Imervue.image import gps, xmp_sidecar
from Imervue.image.geo_keywords import merge_keywords, tag_paths_by_location
from Imervue.image.reverse_geocode import place_keywords


# ---------------------------------------------------------------------------
# merge_keywords (pure)
# ---------------------------------------------------------------------------


def test_merge_appends_new():
    assert merge_keywords(["a"], ["b", "c"]) == ["a", "b", "c"]


def test_merge_dedupes_preserving_order():
    assert merge_keywords(["a", "b"], ["b", "a", "c"]) == ["a", "b", "c"]


def test_merge_skips_empty_strings():
    assert merge_keywords([], ["", "x"]) == ["x"]


# ---------------------------------------------------------------------------
# place_keywords (pure)
# ---------------------------------------------------------------------------


def test_place_keywords_returns_city_and_country():
    assert place_keywords(48.85, 2.35) == ["Paris", "France"]


# ---------------------------------------------------------------------------
# tag_paths_by_location (writes XMP sidecars)
# ---------------------------------------------------------------------------


def test_tag_paths_by_location_writes_and_is_idempotent(tmp_path, monkeypatch):
    geotagged = tmp_path / "a.jpg"
    geotagged.write_bytes(b"\x00")
    plain = tmp_path / "b.jpg"
    plain.write_bytes(b"\x00")
    coords = {str(geotagged): (48.85, 2.35), str(plain): None}
    monkeypatch.setattr(gps, "extract_gps", lambda p: coords.get(str(p)))

    count = tag_paths_by_location([str(geotagged), str(plain)])
    assert count == 1
    keywords = xmp_sidecar.load(str(geotagged)).keywords
    assert "Paris" in keywords
    assert "France" in keywords

    # Re-running leaves the sidecar unchanged.
    assert tag_paths_by_location([str(geotagged)]) == 0
