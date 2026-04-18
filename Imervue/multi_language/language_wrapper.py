from __future__ import annotations

import logging

from Imervue.multi_language.chinese import chinese_word_dict
from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.japanese import japanese_word_dict
from Imervue.multi_language.korean import korean_word_dict
from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict

logger = logging.getLogger("Imervue.language")

# Built-in language codes
BUILTIN_LANGUAGES: list[str] = [
    "English",
    "Traditional_Chinese",
    "Chinese",
    "Korean",
    "Japanese",
]


class LanguageWrapper:

    def __init__(
            self
    ):
        self.language: str = "English"
        self.choose_language_dict: dict[str, dict] = {
            "English": english_word_dict,
            "Traditional_Chinese": traditional_chinese_word_dict,
            "Chinese": chinese_word_dict,
            "Korean": korean_word_dict,
            "Japanese": japanese_word_dict,
        }
        self.language_word_dict: dict = self.choose_language_dict.get(self.language)

        # Plugin-registered languages: {language_code: display_name}
        self.plugin_languages: dict[str, str] = {}

    def reset_language(self, language: str) -> None:
        if language in self.choose_language_dict:
            self.language = language
            self.language_word_dict = self.choose_language_dict.get(self.language)

    def register_language(self, language_code: str, display_name: str, word_dict: dict) -> None:
        """Register a new language from a plugin.

        Args:
            language_code: Internal language code (e.g. "Spanish", "French").
            display_name: Display name shown in the language menu (e.g. "Español").
            word_dict: Full translation dictionary with the same keys as english_word_dict.
        """
        if language_code in BUILTIN_LANGUAGES:
            logger.warning(
                f"Cannot override built-in language '{language_code}' via plugin, "
                f"use merge_translations() to extend it."
            )
            return

        self.choose_language_dict[language_code] = dict(word_dict)
        self.plugin_languages[language_code] = display_name
        logger.info(f"Registered plugin language: {display_name} ({language_code})")

    def merge_translations(self, translations: dict[str, dict[str, str]]) -> None:
        """Merge plugin translation strings into existing languages.

        This allows plugins to add their own UI string keys to each language.
        Existing keys are NOT overwritten to prevent plugins from breaking
        built-in strings.

        Args:
            translations: {language_code: {key: translated_string}}.
                          Language codes not in choose_language_dict are skipped.
        """
        for lang_code, extra_dict in translations.items():
            target = self.choose_language_dict.get(lang_code)
            if target is None:
                logger.debug(f"merge_translations: skipping unknown language '{lang_code}'")
                continue
            for key, value in extra_dict.items():
                if key not in target:
                    target[key] = value


language_wrapper = LanguageWrapper()
