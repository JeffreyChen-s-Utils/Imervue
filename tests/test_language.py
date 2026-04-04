"""Tests for multi-language support."""
import pytest

from Imervue.multi_language.language_wrapper import LanguageWrapper, BUILTIN_LANGUAGES
from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.chinese import chinese_word_dict
from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict
from Imervue.multi_language.japanese import japanese_word_dict
from Imervue.multi_language.korean import korean_word_dict


ALL_DICTS = {
    "English": english_word_dict,
    "Chinese": chinese_word_dict,
    "Traditional_Chinese": traditional_chinese_word_dict,
    "Japanese": japanese_word_dict,
    "Korean": korean_word_dict,
}


class TestLanguageCompleteness:
    """Verify all languages have the same keys as English."""

    def test_all_languages_have_same_keys(self):
        english_keys = set(english_word_dict.keys())
        for lang_name, lang_dict in ALL_DICTS.items():
            if lang_name == "English":
                continue
            lang_keys = set(lang_dict.keys())
            missing = english_keys - lang_keys
            assert not missing, (
                f"{lang_name} is missing keys: {missing}"
            )

    def test_no_extra_keys_in_translations(self):
        english_keys = set(english_word_dict.keys())
        for lang_name, lang_dict in ALL_DICTS.items():
            if lang_name == "English":
                continue
            extra = set(lang_dict.keys()) - english_keys
            assert not extra, (
                f"{lang_name} has extra keys not in English: {extra}"
            )

    def test_no_empty_values(self):
        for lang_name, lang_dict in ALL_DICTS.items():
            for key, value in lang_dict.items():
                assert value is not None, f"{lang_name}[{key}] is None"
                assert isinstance(value, str), f"{lang_name}[{key}] is not a string"
                assert len(value) > 0, f"{lang_name}[{key}] is empty"

    def test_format_placeholders_match_english(self):
        """Translations with {placeholders} should have the same placeholders as English."""
        import re
        placeholder_re = re.compile(r"\{(\w+)\}")

        for key, en_value in english_word_dict.items():
            en_placeholders = set(placeholder_re.findall(en_value))
            if not en_placeholders:
                continue
            for lang_name, lang_dict in ALL_DICTS.items():
                if lang_name == "English":
                    continue
                lang_value = lang_dict.get(key, "")
                lang_placeholders = set(placeholder_re.findall(lang_value))
                assert en_placeholders == lang_placeholders, (
                    f"{lang_name}[{key}]: placeholders {lang_placeholders} "
                    f"!= English {en_placeholders}"
                )


class TestLanguageWrapper:
    def test_default_language(self):
        lw = LanguageWrapper()
        assert lw.language == "English"
        assert lw.language_word_dict is english_word_dict

    def test_reset_language(self):
        lw = LanguageWrapper()
        lw.reset_language("Japanese")
        assert lw.language == "Japanese"
        assert lw.language_word_dict is japanese_word_dict

    def test_reset_invalid_language(self):
        lw = LanguageWrapper()
        lw.reset_language("Klingon")
        # Should stay on English
        assert lw.language == "English"

    def test_builtin_languages(self):
        assert "English" in BUILTIN_LANGUAGES
        assert "Chinese" in BUILTIN_LANGUAGES
        assert "Traditional_Chinese" in BUILTIN_LANGUAGES
        assert "Japanese" in BUILTIN_LANGUAGES
        assert "Korean" in BUILTIN_LANGUAGES

    def test_register_plugin_language(self):
        lw = LanguageWrapper()
        lw.register_language("Spanish", "Espanol", {"key1": "valor1"})
        assert "Spanish" in lw.choose_language_dict
        assert "Spanish" in lw.plugin_languages
        lw.reset_language("Spanish")
        assert lw.language_word_dict["key1"] == "valor1"

    def test_cannot_override_builtin(self):
        lw = LanguageWrapper()
        original = lw.choose_language_dict["English"]
        lw.register_language("English", "English", {"hacked": "yes"})
        # Should not have changed
        assert lw.choose_language_dict["English"] is original

    def test_merge_translations(self):
        lw = LanguageWrapper()
        lw.merge_translations({
            "English": {"plugin_key": "Plugin Value"},
            "Japanese": {"plugin_key": "Plugin JP"},
        })
        assert lw.choose_language_dict["English"].get("plugin_key") == "Plugin Value"
        # Cleanup
        english_word_dict.pop("plugin_key", None)
        japanese_word_dict.pop("plugin_key", None)
