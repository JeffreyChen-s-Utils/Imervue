"""_load must reject a corrupt (non-list) recent-files setting.

A bare string is iterable, so the old ``isinstance(raw, Iterable)`` check let a
corrupt ``"abc"`` through and split it into one entry per character.
"""
from __future__ import annotations

from Imervue.paint.recent_files import RECENT_FILES_KEY, _load
from Imervue.user_settings.user_setting_dict import user_setting_dict


def test_load_rejects_a_corrupt_string_setting():
    user_setting_dict[RECENT_FILES_KEY] = "abc"
    assert _load() == []          # not ["a", "b", "c"]


def test_load_filters_non_string_and_empty_entries():
    user_setting_dict[RECENT_FILES_KEY] = ["/a.png", "", 123, "/b.png"]
    assert _load() == ["/a.png", "/b.png"]


def test_load_missing_setting_is_empty():
    user_setting_dict.pop(RECENT_FILES_KEY, None)
    assert _load() == []
