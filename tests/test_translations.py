"""
Tests for translation completeness — every key in English must exist in all
other languages.

No Qt dependency.
"""
from __future__ import annotations

import pytest

from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict
from Imervue.multi_language.chinese import chinese_word_dict
from Imervue.multi_language.japanese import japanese_word_dict
from Imervue.multi_language.korean import korean_word_dict


_ALL_LANGS = {
    "traditional_chinese": traditional_chinese_word_dict,
    "chinese": chinese_word_dict,
    "japanese": japanese_word_dict,
    "korean": korean_word_dict,
}


class TestTranslationCompleteness:
    @pytest.mark.parametrize("lang_name,lang_dict", list(_ALL_LANGS.items()))
    def test_all_english_keys_present(self, lang_name, lang_dict):
        missing = set(english_word_dict.keys()) - set(lang_dict.keys())
        assert not missing, (
            f"{lang_name} is missing {len(missing)} translation keys: "
            f"{sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}"
        )

    @pytest.mark.parametrize("lang_name,lang_dict", list(_ALL_LANGS.items()))
    def test_no_empty_values(self, lang_name, lang_dict):
        empty = [k for k, v in lang_dict.items() if not v.strip()]
        assert not empty, (
            f"{lang_name} has empty translation values for: {empty[:10]}"
        )


class TestTranslationNewFeatures:
    """Verify that newly added feature keys exist in all languages."""

    _CROP_KEYS = [
        "annotation_tool_crop", "crop_apply", "crop_cancel",
        "crop_ratio_free", "crop_ratio_1_1", "crop_ratio_4_3",
        "crop_ratio_3_2", "crop_ratio_16_9", "crop_ratio_9_16",
    ]

    _DUPLICATE_KEYS = [
        "duplicate_title", "duplicate_source", "duplicate_method",
        "duplicate_exact", "duplicate_perceptual", "duplicate_threshold",
        "duplicate_recursive", "duplicate_scan", "duplicate_scanning",
        "duplicate_no_duplicates", "duplicate_found",
        "duplicate_col_filename", "duplicate_col_path", "duplicate_col_size",
        "duplicate_delete_selected", "duplicate_confirm_title",
        "duplicate_confirm_msg", "duplicate_deleted",
    ]

    _SHORTCUT_KEYS = [
        "shortcut_title", "shortcut_info", "shortcut_col_action",
        "shortcut_col_shortcut", "shortcut_col_default",
        "shortcut_reset", "shortcut_save",
    ]

    _EXTRA_TOOLS_KEYS = [
        "extra_tools_menu",
    ]

    _BATCH_CONVERT_KEYS = [
        "batch_convert_title", "batch_convert_source",
    ]

    _UPSCALE_KEYS = [
        "upscale_title",
    ]

    _ORGANIZER_KEYS = [
        "organizer_title", "organizer_source", "organizer_rule",
        "organizer_rule_date", "organizer_rule_resolution",
        "organizer_rule_type", "organizer_rule_size", "organizer_rule_count",
        "organizer_output", "organizer_mode_copy", "organizer_mode_move",
        "organizer_preview", "organizer_start",
    ]

    _EXIF_STRIP_KEYS = [
        "exif_strip_title", "exif_strip_source", "exif_strip_info",
        "exif_strip_overwrite", "exif_strip_no_images",
        "exif_strip_processing", "exif_strip_done",
    ]

    @pytest.mark.parametrize("key", _CROP_KEYS)
    def test_crop_key_in_english(self, key):
        assert key in english_word_dict, f"Missing crop key in English: {key}"

    @pytest.mark.parametrize("key", _CROP_KEYS)
    def test_crop_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing crop key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _DUPLICATE_KEYS)
    def test_duplicate_key_in_english(self, key):
        assert key in english_word_dict, f"Missing duplicate key in English: {key}"

    @pytest.mark.parametrize("key", _DUPLICATE_KEYS)
    def test_duplicate_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing duplicate key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _SHORTCUT_KEYS)
    def test_shortcut_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing shortcut key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _EXTRA_TOOLS_KEYS)
    def test_extra_tools_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing extra tools key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _BATCH_CONVERT_KEYS)
    def test_batch_convert_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing batch convert key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _UPSCALE_KEYS)
    def test_upscale_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing upscale key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _ORGANIZER_KEYS)
    def test_organizer_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing organizer key '{key}' in {lang_name}"
            )

    @pytest.mark.parametrize("key", _EXIF_STRIP_KEYS)
    def test_exif_strip_key_in_all_langs(self, key):
        for lang_name, lang_dict in _ALL_LANGS.items():
            assert key in lang_dict, (
                f"Missing EXIF strip key '{key}' in {lang_name}"
            )
