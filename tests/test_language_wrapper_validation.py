"""Plugin languages and translations are checked before they reach the UI.

``multi_language/translation_validation.py`` (key, empty-value and placeholder
checks) was tested but unreachable, so a plugin string with the wrong
``{placeholder}`` made ``.format()`` raise ``KeyError`` in the middle of the UI.
``register_language`` and ``merge_translations`` now log what is wrong and drop
the strings that would break, so the built-in text shows instead.
"""
from __future__ import annotations

import logging

import pytest

from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.language_wrapper import LanguageWrapper, usable_strings

_KEY = "contact_sheet_source"          # English: "{count} image(s) will be included."


@pytest.fixture
def wrapper():
    return LanguageWrapper()


def test_usable_strings_drops_empty_and_mismatched_values():
    reference = {"a": "Hello {name}", "b": "Plain"}
    strings = {"a": "Hola {nombre}", "b": "  ", "c": "new {x}", "d": 3}
    assert usable_strings(reference, strings) == {"c": "new {x}"}
    assert usable_strings(reference, {"a": "Hola {name}"}) == {"a": "Hola {name}"}


def test_a_plugin_language_loses_only_its_broken_strings(wrapper, caplog):
    words = {_KEY: "{cuenta} imágenes", "contact_sheet_rows": "Filas", "tag_close": ""}
    with caplog.at_level(logging.INFO, logger="Imervue.language"):
        wrapper.register_language("Spanish", "Español", words)
    registered = wrapper.choose_language_dict["Spanish"]
    assert registered == {"contact_sheet_rows": "Filas"}
    text = caplog.text
    assert "Plugin language 'Spanish'" in text and "placeholder mismatch" in text
    assert "empty value" in text and "lacks" in text
    wrapper.reset_language("Spanish")
    assert wrapper.language_word_dict.get(_KEY, english_word_dict[_KEY]).format(count=3) == (
        "3 image(s) will be included.")


def test_a_correct_plugin_language_logs_no_warning(wrapper, caplog):
    with caplog.at_level(logging.WARNING, logger="Imervue.language"):
        wrapper.register_language("Klingon", "tlhIngan", dict(english_word_dict))
    assert caplog.text == ""
    assert wrapper.choose_language_dict["Klingon"] == english_word_dict


def test_merged_translations_follow_the_payloads_english(wrapper, caplog):
    payload = {
        "English": {"my_plugin_done": "Saved {path}"},
        "Traditional_Chinese": {"my_plugin_done": "已儲存 {路徑}"},
        "Japanese": {"my_plugin_done": "{path} を保存しました"},
        "Klingon": {"my_plugin_done": "{path}"},
    }
    with caplog.at_level(logging.WARNING, logger="Imervue.language"):
        wrapper.merge_translations(payload)
    tables = wrapper.choose_language_dict
    assert tables["English"]["my_plugin_done"] == "Saved {path}"
    assert tables["Japanese"]["my_plugin_done"] == "{path} を保存しました"
    assert "my_plugin_done" not in tables["Traditional_Chinese"]
    assert "not registered" in caplog.text and "placeholder mismatch" in caplog.text


def test_merging_never_overwrites_a_built_in_string(wrapper):
    wrapper.merge_translations({"English": {_KEY: "{count} pictures"}})
    assert wrapper.choose_language_dict["English"][_KEY] == english_word_dict[_KEY]


def test_a_merged_string_breaking_a_built_in_placeholder_is_dropped(wrapper):
    wrapper.merge_translations({"Korean": {"brand_new_key": "ok", _KEY: "{n}"}})
    assert wrapper.choose_language_dict["Korean"]["brand_new_key"] == "ok"
