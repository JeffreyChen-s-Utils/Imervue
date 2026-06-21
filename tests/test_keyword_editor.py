"""Tests for the keyword/IPTC metadata editor."""
from __future__ import annotations

import pytest

# The editor writes through xmp_sidecar, which needs defusedxml.
pytest.importorskip("defusedxml")

from Imervue.gui.keyword_editor_dialog import (
    keywords_to_text,
    parse_keywords,
    rank_suggestions,
)
from Imervue.library import image_index


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    # _save mirrors keywords into the tag index; keep that off the real DB.
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


# ---------------------------------------------------------------------------
# parse_keywords / keywords_to_text (pure)
# ---------------------------------------------------------------------------


def test_parse_keywords_strips_and_dedupes():
    assert parse_keywords("a, b ,a,  , c") == ["a", "b", "c"]


def test_parse_keywords_empty():
    assert parse_keywords("   ") == []


def test_keywords_to_text_round_trip():
    assert keywords_to_text(["a", "b"]) == "a, b"
    assert parse_keywords(keywords_to_text(["x", "y"])) == ["x", "y"]


# ---------------------------------------------------------------------------
# rank_suggestions (pure)
# ---------------------------------------------------------------------------


def test_rank_suggestions_aggregates_and_excludes_present():
    related = {
        "beach": [("sunset", 3), ("ocean", 2)],
        "vacation": [("sunset", 1), ("beach", 5)],  # 'beach' present -> excluded
    }
    assert rank_suggestions(["beach", "vacation"], related) == ["sunset", "ocean"]


def test_rank_suggestions_ties_broken_by_name():
    assert rank_suggestions(["a"], {"a": [("y", 1), ("x", 1)]}) == ["x", "y"]


def test_rank_suggestions_limit_caps():
    related = {"a": [("p", 3), ("q", 2), ("r", 1)]}
    assert rank_suggestions(["a"], related, limit=2) == ["p", "q"]


def test_rank_suggestions_empty():
    assert rank_suggestions([], {}) == []


# ---------------------------------------------------------------------------
# Qt smoke — editing writes an XMP sidecar
# ---------------------------------------------------------------------------


def test_dialog_smoke_saves_xmp(qapp, tmp_path):
    from Imervue.gui.keyword_editor_dialog import KeywordEditorDialog
    from Imervue.image import xmp_sidecar

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\x00")
    dialog = KeywordEditorDialog(object(), str(path))
    try:
        dialog._title_edit.setText("Sunset")
        dialog._creator_edit.setText("Jane Doe")
        dialog._keywords_edit.setText("beach, sunset, beach")
        dialog._save()
    finally:
        dialog.deleteLater()

    loaded = xmp_sidecar.load(str(path))
    assert loaded.title == "Sunset"
    assert loaded.creator == "Jane Doe"
    assert loaded.keywords == ["beach", "sunset"]
    # Saving also mirrors keywords into the searchable tag index.
    assert set(image_index.tags_of_image(str(path))) == {"beach", "sunset"}


def _suggestion_labels(dialog):
    from PySide6.QtWidgets import QPushButton
    row = dialog._suggestions_row
    labels = []
    for i in range(row.count()):
        widget = row.itemAt(i).widget()
        if isinstance(widget, QPushButton):
            labels.append(widget.text())
    return labels


def test_dialog_suggests_and_adds_related_tag(qapp, tmp_path):
    from Imervue.gui.keyword_editor_dialog import KeywordEditorDialog
    # Co-occurrence in the index: beach & sunset together on two images.
    for p in ("x.png", "y.png"):
        image_index.add_image_tag(p, "beach")
        image_index.add_image_tag(p, "sunset")
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\x00")
    dialog = KeywordEditorDialog(object(), str(path))
    try:
        dialog._keywords_edit.setText("beach")
        dialog._refresh_suggestions()
        assert any("sunset" in label for label in _suggestion_labels(dialog))
        dialog._add_keyword("sunset")
        assert "sunset" in parse_keywords(dialog._keywords_edit.text())
    finally:
        dialog.deleteLater()
