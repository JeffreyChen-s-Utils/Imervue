"""Tests for settings_notice: the start-up warning about an unreadable settings file."""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.gui.settings_notice import warn_if_settings_unreadable


def _broken_settings(tmp_path):
    path = tmp_path / "user_setting.json"
    path.write_text('{"profiles": {', encoding="utf-8")
    return path


def test_nothing_to_tell_when_the_settings_were_read(qapp, tmp_path):
    from Imervue.user_settings.user_setting_dict import read_user_setting, write_user_setting
    write_user_setting()
    read_user_setting()
    assert warn_if_settings_unreadable(None) is None


def test_nothing_to_tell_without_a_settings_file(qapp):
    from Imervue.user_settings.user_setting_dict import read_user_setting
    read_user_setting()
    assert warn_if_settings_unreadable(None) is None


def test_an_unreadable_file_is_named_with_where_its_copy_goes(qapp, tmp_path):
    from Imervue.user_settings.user_setting_dict import read_user_setting
    path = _broken_settings(tmp_path)
    read_user_setting()
    box = warn_if_settings_unreadable(None)
    try:
        assert box is not None
        assert box.isVisible()
        assert box.windowTitle() == "Settings could not be read"
        assert str(path) in box.text()
        assert "user_setting.json.unreadable-<date>-<time>" in box.text()
        assert box.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    finally:
        box.close()


def test_the_warning_follows_the_ui_language(qapp, tmp_path):
    from Imervue.multi_language.language_wrapper import language_wrapper
    from Imervue.user_settings.user_setting_dict import read_user_setting
    _broken_settings(tmp_path)
    read_user_setting()
    previous = language_wrapper.language
    language_wrapper.reset_language("Traditional_Chinese")
    try:
        box = warn_if_settings_unreadable(None)
    finally:
        language_wrapper.reset_language(previous)
    try:
        assert box.windowTitle() == "無法讀取設定檔"
        assert "改名為 user_setting.json" in box.text()
    finally:
        box.close()
