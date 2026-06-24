"""Tests for caption code-replacement expansion."""
from __future__ import annotations

import pytest

from Imervue.user_settings.code_replacements import expand_codes


# ---------------------------------------------------------------------------
# code substitution
# ---------------------------------------------------------------------------


def test_no_codes_returns_text_unchanged():
    assert expand_codes("plain caption", {}) == "plain caption"


def test_single_code_expands():
    out = expand_codes("\\wch event", {"wch": "Wedding ceremony"})
    assert out == "Wedding ceremony event"


def test_code_at_string_start_and_end():
    out = expand_codes("\\a mid \\b", {"a": "ALPHA", "b": "BETA"})
    assert out == "ALPHA mid BETA"


def test_unknown_code_left_verbatim():
    assert expand_codes("\\xyz here", {"wch": "x"}) == "\\xyz here"


def test_custom_delimiter():
    out = expand_codes("@loc today", {"loc": "Paris"}, delimiter="@")
    assert out == "Paris today"


# ---------------------------------------------------------------------------
# variable substitution
# ---------------------------------------------------------------------------


def test_variable_filled_from_meta():
    out = expand_codes("Shot in {city}", {}, {"city": "Berlin"})
    assert out == "Shot in Berlin"


def test_unknown_variable_left_verbatim():
    assert expand_codes("Shot in {city}", {}, {}) == "Shot in {city}"


def test_code_expands_then_variable():
    out = expand_codes(
        "\\loc",
        {"loc": "{city}, {country}"},
        {"city": "Paris", "country": "France"},
    )
    assert out == "Paris, France"


def test_non_string_variable_coerced():
    out = expand_codes("ISO {iso}", {}, {"iso": 400})
    assert out == "ISO 400"


# ---------------------------------------------------------------------------
# recursion guard & errors
# ---------------------------------------------------------------------------


def test_self_referential_code_does_not_loop():
    # A code whose replacement re-emits itself must terminate, not hang.
    out = expand_codes("\\a", {"a": "\\a"})
    assert out == "\\a"


def test_nested_code_chain_resolves():
    out = expand_codes("\\a", {"a": "\\b end", "b": "start"})
    assert out == "start end"


def test_empty_delimiter_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        expand_codes("\\a", {"a": "x"}, delimiter="")


def test_rejects_non_string_text():
    with pytest.raises(TypeError, match="text must be str"):
        expand_codes(123, {})


def test_rejects_non_dict_codes():
    with pytest.raises(TypeError, match="codes must be a dict"):
        expand_codes("x", ["not", "a", "dict"])
