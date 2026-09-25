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


# ---------------------------------------------------------------------------
# Keyword hierarchies (lr:hierarchicalSubject)
# ---------------------------------------------------------------------------


def test_tag_paths_turns_a_hierarchy_into_a_tag_path():
    from Imervue.library.keyword_index import tag_paths
    assert tag_paths(["Places", "Taiwan", "Taipei", "night"],
                     ["Places|Taiwan|Taipei", " Trips | 2024 "]) == [
        "Places/Taiwan/Taipei", "Trips/2024", "night"]


@pytest.mark.parametrize(("keywords", "hierarchical", "expected"), [
    ([], [], []),
    (["a"], [], ["a"]),
    ([], ["|", ""], []),                 # empty levels only: nothing
    ([], ["Solo"], ["Solo"]),            # a one-level hierarchy is a plain tag
])
def test_tag_paths_edge_cases(keywords, hierarchical, expected):
    from Imervue.library.keyword_index import tag_paths
    assert tag_paths(keywords, hierarchical) == expected


def test_import_files_a_lightroom_hierarchy_under_its_parents(tmp_path):
    """Lightroom's Places > Taiwan > Taipei landed as three loose tags."""
    from Imervue.image import xmp_sidecar

    photo = tmp_path / "p.jpg"
    photo.write_bytes(b"\x00")
    xmp_sidecar.sidecar_path_for(str(photo)).write_text(
        """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
   <dc:subject><rdf:Bag><rdf:li>Places</rdf:li><rdf:li>Taiwan</rdf:li>
    <rdf:li>Taipei</rdf:li><rdf:li>night</rdf:li></rdf:Bag></dc:subject>
   <lr:hierarchicalSubject><rdf:Bag><rdf:li>Places|Taiwan|Taipei</rdf:li>
    </rdf:Bag></lr:hierarchicalSubject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>""", encoding="utf-8")

    assert import_keywords_to_index([str(photo)]) == 1
    assert sorted(image_index.tags_of_image(str(photo))) == ["Places/Taiwan/Taipei", "night"]
    assert str(photo) in image_index.images_with_tag("Places")   # found from the parent too
