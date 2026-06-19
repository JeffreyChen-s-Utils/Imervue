"""Tests for OCR TSV parsing and the optional-backend guard."""
from __future__ import annotations

import pytest

from Imervue.image import ocr
from Imervue.image.ocr import (
    OcrUnavailableError,
    extract_words,
    ocr_available,
    parse_tsv,
    words_to_text,
)

_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
_TSV = "\n".join([
    _HEADER,
    "5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t95.5\tHello",
    "5\t1\t1\t1\t1\t2\t70\t10\t60\t20\t90.0\tWorld",
    "5\t1\t1\t1\t2\t1\t10\t40\t40\t20\t30.0\tlow",
    "4\t1\t1\t1\t2\t0\t0\t0\t0\t0\t-1\t",
])


# ---------------------------------------------------------------------------
# parse_tsv
# ---------------------------------------------------------------------------


def test_parse_tsv_confidence_filter():
    words = parse_tsv(_TSV, min_confidence=50.0)
    assert [w.text for w in words] == ["Hello", "World"]


def test_parse_tsv_keeps_low_confidence_when_threshold_zero():
    words = parse_tsv(_TSV, min_confidence=0.0)
    assert [w.text for w in words] == ["Hello", "World", "low"]


def test_parse_tsv_word_fields():
    first = parse_tsv(_TSV)[0]
    assert first.text == "Hello"
    assert first.confidence == 95.5  # NOSONAR - exact parsed value
    assert (first.left, first.top, first.width, first.height) == (10, 10, 50, 20)


def test_parse_tsv_empty_input():
    assert parse_tsv("") == []


def test_parse_tsv_missing_columns():
    assert parse_tsv("foo\tbar\nx\ty") == []


# ---------------------------------------------------------------------------
# words_to_text
# ---------------------------------------------------------------------------


def test_words_to_text_groups_by_line():
    assert words_to_text(parse_tsv(_TSV, 0.0)) == "Hello World\nlow"


def test_words_to_text_empty():
    assert words_to_text([]) == ""


# ---------------------------------------------------------------------------
# availability guard
# ---------------------------------------------------------------------------


def test_ocr_available_returns_bool():
    assert isinstance(ocr_available(), bool)


def test_extract_words_raises_when_unavailable(monkeypatch):
    monkeypatch.setattr(ocr, "ocr_available", lambda: False)
    with pytest.raises(OcrUnavailableError):
        extract_words("nonexistent.png")


# ---------------------------------------------------------------------------
# dialog smoke (no Tesseract needed — drive _on_done directly)
# ---------------------------------------------------------------------------


def test_dialog_shows_text(qapp):
    from Imervue.gui.ocr_dialog import OcrDialog

    dialog = OcrDialog(object(), "scene.png")
    try:
        dialog._on_done(True, "Hello\nWorld")
        assert dialog._text.toPlainText() == "Hello\nWorld"
        dialog._on_done(False, "boom")
        assert dialog._text.toPlainText() == "boom"
        dialog._on_done(True, "")
        assert dialog._text.toPlainText() != ""  # empty → fallback message
    finally:
        dialog.deleteLater()
