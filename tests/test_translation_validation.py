"""Tests for translation dictionary validation helpers."""
from __future__ import annotations

from Imervue.multi_language.translation_validation import (
    compare_keys,
    extract_placeholders,
    find_empty_values,
    find_placeholder_mismatches,
    validate_merge_payload,
    validate_translation,
)

_REFERENCE = {"file": "File", "open_n": "Open {count} files", "save": "Save"}


# ---------------------------------------------------------------------------
# extract_placeholders
# ---------------------------------------------------------------------------


def test_extract_placeholders():
    assert extract_placeholders("Open {count} of {total}") == {"count", "total"}


def test_extract_placeholders_none_text():
    assert extract_placeholders(None) == set()  # NOSONAR: negative test of the non-str guard
    assert extract_placeholders("plain") == set()


# ---------------------------------------------------------------------------
# compare_keys / find_empty_values / find_placeholder_mismatches
# ---------------------------------------------------------------------------


def test_compare_keys_missing_and_extra():
    missing, extra = compare_keys(_REFERENCE, {"file": "F", "bonus": "B"})
    assert missing == {"open_n", "save"}
    assert extra == {"bonus"}


def test_find_empty_values_catches_blank_and_non_str():
    bad = {"a": "ok", "b": "", "c": "   ", "d": None, "e": 5}
    assert set(find_empty_values(bad)) == {"b", "c", "d", "e"}


def test_find_placeholder_mismatches():
    candidate = {"file": "Datei", "open_n": "Open files", "save": "Speichern"}
    mismatches = find_placeholder_mismatches(_REFERENCE, candidate)
    assert len(mismatches) == 1
    key, ref_ph, cand_ph = mismatches[0]
    assert key == "open_n"
    assert ref_ph == {"count"}
    assert cand_ph == set()


# ---------------------------------------------------------------------------
# validate_translation
# ---------------------------------------------------------------------------


def test_validate_translation_clean():
    candidate = {"file": "Datei", "open_n": "Öffne {count}", "save": "Speichern"}
    assert validate_translation(_REFERENCE, candidate) == []


def test_validate_translation_reports_missing_keys():
    errors = validate_translation(_REFERENCE, {"file": "Datei"})
    assert any("missing 2 key(s)" in e for e in errors)


def test_validate_translation_partial_allowed_when_not_required():
    errors = validate_translation(
        _REFERENCE, {"file": "Datei"}, require_all_keys=False)
    assert errors == []


def test_validate_translation_reports_extra_and_empty_and_placeholder():
    candidate = {
        "file": "Datei",
        "open_n": "Öffne Dateien",   # dropped {count}
        "save": "",                   # empty
        "extra": "X",                 # not in reference
    }
    errors = validate_translation(_REFERENCE, candidate)
    assert any("unknown key" in e for e in errors)
    assert any("empty value" in e for e in errors)
    assert any("placeholder mismatch for 'open_n'" in e for e in errors)


def test_validate_translation_sample_truncates_long_lists():
    reference = {f"k{i}": str(i) for i in range(25)}
    errors = validate_translation(reference, {})
    assert any("more)" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_merge_payload
# ---------------------------------------------------------------------------


def test_validate_merge_payload_clean():
    payload = {
        "English": {"plugin_hi": "Hi {name}"},
        "Japanese": {"plugin_hi": "こんにちは {name}"},
    }
    assert validate_merge_payload(
        payload, known_languages={"English", "Japanese"}) == []


def test_validate_merge_payload_flags_unknown_language():
    payload = {"Klingon": {"plugin_hi": "nuqneH"}}
    errors = validate_merge_payload(payload, known_languages={"English"})
    assert any("not registered" in e for e in errors)


def test_validate_merge_payload_flags_inconsistent_keys():
    payload = {
        "English": {"plugin_hi": "Hi", "plugin_bye": "Bye"},
        "Japanese": {"plugin_hi": "やあ"},  # missing plugin_bye
    }
    errors = validate_merge_payload(payload)
    assert any("Japanese: missing 1 key(s)" in e for e in errors)


def test_validate_merge_payload_flags_placeholder_mismatch_across_languages():
    payload = {
        "English": {"plugin_hi": "Hi {name}"},
        "Japanese": {"plugin_hi": "やあ"},  # dropped {name}
    }
    errors = validate_merge_payload(payload)
    assert any("placeholder mismatch for 'plugin_hi'" in e for e in errors)


def test_validate_merge_payload_empty_payload():
    assert validate_merge_payload({}) == []


def test_validate_merge_payload_no_known_languages_skips_registration_check():
    payload = {"Anything": {"plugin_hi": "Hi"}}
    # Without known_languages we only check internal consistency, not registration.
    assert validate_merge_payload(payload) == []
