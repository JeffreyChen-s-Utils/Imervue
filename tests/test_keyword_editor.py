"""Tests for the keyword/IPTC metadata editor."""
from __future__ import annotations

import pytest

# The editor writes through xmp_sidecar, which needs defusedxml.
pytest.importorskip("defusedxml")

from Imervue.gui.keyword_editor_dialog import keywords_to_text, parse_keywords


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
