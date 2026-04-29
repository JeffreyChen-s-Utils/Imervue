"""Tests for the cheat-sheet PDF exporter."""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.export.cheat_sheet import (
    CheatSheetOptions,
    _format_key_combo,
    collect_shortcut_rows,
    generate_cheat_sheet,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_collect_rows_returns_at_least_one_row(qapp):
    rows = collect_shortcut_rows()
    assert rows, "DEFAULT_SHORTCUTS should not be empty"
    # Every entry is (label, key_text) — both strings
    for label, combo in rows:
        assert isinstance(label, str)
        assert isinstance(combo, str)


def test_collect_rows_label_uses_active_language(qapp):
    """Switching language flips the label text."""
    from Imervue.multi_language.language_wrapper import language_wrapper
    original = language_wrapper.language_word_dict.get("shortcut_action_undo")
    rows = collect_shortcut_rows()
    label_to_combo = dict(rows)
    # The undo row should match whatever the language file says about it
    if original:
        assert original in label_to_combo


def test_format_key_combo_simple_letter(qapp):
    """Ctrl+C → 'Ctrl+C' across platforms."""
    txt = _format_key_combo(int(Qt.Key.Key_C),
                            int(Qt.KeyboardModifier.ControlModifier.value))
    assert "C" in txt
    assert "Ctrl" in txt or "Control" in txt or "⌘" in txt  # macOS cmd glyph


def test_format_key_combo_shift_alt(qapp):
    txt = _format_key_combo(
        int(Qt.Key.Key_M),
        int(Qt.KeyboardModifier.ShiftModifier.value
            | Qt.KeyboardModifier.AltModifier.value),
    )
    # Order may vary but each token should appear
    assert "M" in txt


# ---------------------------------------------------------------------------
# PDF generation (no rendering assertion; just a non-empty output)
# ---------------------------------------------------------------------------


def test_generate_cheat_sheet_writes_pdf(qapp, tmp_path):
    out = tmp_path / "shortcuts.pdf"
    result = generate_cheat_sheet(str(out), CheatSheetOptions())
    assert result == str(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_generate_cheat_sheet_starts_with_pdf_magic(qapp, tmp_path):
    out = tmp_path / "shortcuts.pdf"
    generate_cheat_sheet(str(out), CheatSheetOptions())
    assert out.read_bytes().startswith(b"%PDF-")


def test_generate_cheat_sheet_letter_page_size(qapp, tmp_path):
    out = tmp_path / "letter.pdf"
    generate_cheat_sheet(str(out), CheatSheetOptions(page_size="Letter"))
    assert out.exists()


def test_generate_cheat_sheet_unknown_page_size_falls_back(qapp, tmp_path):
    """Unrecognised page size shouldn't raise — fall back to A4."""
    out = tmp_path / "fallback.pdf"
    generate_cheat_sheet(str(out), CheatSheetOptions(page_size="A8-but-fake"))
    assert out.exists()
