"""Tests for importing XMP keywords into the library tag index."""
from __future__ import annotations

import pytest

pytest.importorskip("defusedxml")

from Imervue.library import image_index
from Imervue.library.keyword_index import import_keywords_to_index, new_keywords


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


# ---------------------------------------------------------------------------
# new_keywords (pure)
# ---------------------------------------------------------------------------


def test_new_keywords_diffs_existing():
    assert new_keywords(["a"], ["a", "b", "b", "c"]) == ["b", "c"]


def test_new_keywords_all_new():
    assert new_keywords([], ["x", "y"]) == ["x", "y"]


def test_new_keywords_none_new():
    assert new_keywords(["a", "b"], ["a", "b"]) == []


# ---------------------------------------------------------------------------
# import_keywords_to_index (reads XMP, writes tags)
# ---------------------------------------------------------------------------


def test_import_indexes_xmp_keywords(tmp_path):
    from Imervue.image import xmp_sidecar

    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\x00")
    xmp_sidecar.save(str(photo), xmp_sidecar.XmpData(keywords=["Paris", "France"]))

    assert import_keywords_to_index([str(photo)]) == 1
    assert set(image_index.tags_of_image(str(photo))) == {"Paris", "France"}
    # Re-running adds nothing new.
    assert import_keywords_to_index([str(photo)]) == 0


def test_import_skips_paths_without_keywords(tmp_path):
    photo = tmp_path / "q.jpg"
    photo.write_bytes(b"\x00")
    assert import_keywords_to_index([str(photo)]) == 0
