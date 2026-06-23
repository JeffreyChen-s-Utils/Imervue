"""Tests for settings-backed keyword-vocabulary storage."""
from __future__ import annotations

from Imervue.library.keyword_vocabulary_store import (
    expand_with_stored_vocabulary,
    get_vocabulary_text,
    load_vocabulary,
    set_vocabulary_text,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict

_SAMPLE = "animal\n\tdog\n\t\tLabrador {lab}\n"


def test_default_is_empty():
    # The autouse _isolate_user_settings fixture gives each test a clean dict.
    assert get_vocabulary_text() == ""
    assert load_vocabulary() == []


def test_set_get_round_trip():
    set_vocabulary_text(_SAMPLE)
    assert get_vocabulary_text() == _SAMPLE


def test_non_string_stored_reads_as_empty():
    user_setting_dict["keyword_vocabulary"] = 1234  # corrupt value
    assert get_vocabulary_text() == ""


def test_load_vocabulary_parses_stored_text():
    set_vocabulary_text(_SAMPLE)
    vocab = load_vocabulary()
    assert len(vocab) == 1
    assert vocab[0].name == "animal"


def test_expand_uses_stored_vocabulary():
    set_vocabulary_text(_SAMPLE)
    assert expand_with_stored_vocabulary(["Labrador"]) == [
        "Labrador", "lab", "dog", "animal"]


def test_expand_without_vocabulary_keeps_keywords():
    assert expand_with_stored_vocabulary(["beach", "beach", "sky"]) == ["beach", "sky"]
