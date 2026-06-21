"""Tests for Smart Album export / import (``Imervue.library.album_io``)."""
from __future__ import annotations

import json

import pytest

from Imervue.library import album_io, image_index, smart_album


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


# ---------------------------------------------------------------------------
# parse_albums (pure)
# ---------------------------------------------------------------------------


def test_parse_albums_reads_valid_document():
    text = json.dumps({"version": 1, "albums": [
        {"name": "Faves", "rules": {"min_rating": 4}},
    ]})
    assert album_io.parse_albums(text) == [
        {"name": "Faves", "rules": {"min_rating": 4}}]


def test_parse_albums_skips_malformed_entries():
    text = json.dumps({"albums": [
        {"name": "ok", "rules": {"min_rating": 3}},
        {"name": "", "rules": {}},          # empty name
        {"name": "norule"},                 # missing rules
        {"rules": {"min_rating": 1}},       # missing name
        "not-an-object",
        {"name": "badrule", "rules": "x"},  # rules not a dict
    ]})
    assert album_io.parse_albums(text) == [
        {"name": "ok", "rules": {"min_rating": 3}}]


def test_parse_albums_empty_list():
    assert album_io.parse_albums(json.dumps({"albums": []})) == []


def test_parse_albums_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        album_io.parse_albums(json.dumps([1, 2, 3]))


def test_parse_albums_rejects_missing_albums_key():
    with pytest.raises(ValueError, match="albums"):
        album_io.parse_albums(json.dumps({"version": 1}))


def test_parse_albums_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid album document"):
        album_io.parse_albums("{not json")


# ---------------------------------------------------------------------------
# File round-trip over an isolated index
# ---------------------------------------------------------------------------


def test_export_import_round_trip(tmp_path):
    smart_album.save("Faves", {"min_rating": 4})
    smart_album.save("Landscapes", {"min_aspect": 1.5})
    dest = tmp_path / "albums.json"
    assert album_io.export_albums(dest) == 2

    image_index.close()
    image_index.set_db_path(tmp_path / "library2.db")
    assert album_io.import_albums(dest) == 2
    restored = {a["name"]: a["rules"] for a in smart_album.list_all()}
    assert restored["Faves"] == {"min_rating": 4}
    assert restored["Landscapes"] == {"min_aspect": 1.5}


def test_import_skips_existing_unless_overwrite(tmp_path):
    smart_album.save("A", {"min_rating": 2})
    dest = tmp_path / "a.json"
    album_io.export_albums(dest)
    # Mutate A in the DB; the file still holds the original rules.
    smart_album.save("A", {"min_rating": 5})

    assert album_io.import_albums(dest, overwrite=False) == 0
    assert smart_album.get("A")["rules"] == {"min_rating": 5}

    assert album_io.import_albums(dest, overwrite=True) == 1
    assert smart_album.get("A")["rules"] == {"min_rating": 2}


def test_export_empty_library_writes_zero(tmp_path):
    dest = tmp_path / "empty.json"
    assert album_io.export_albums(dest) == 0
    assert album_io.parse_albums(dest.read_text(encoding="utf-8")) == []
