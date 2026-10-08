"""Tests for the theme registry and apply pipeline."""
from __future__ import annotations

import pytest

from Imervue.system.themes import (
    DEFAULT_THEME_NAME,
    MODERN_OFFERED_KEY,
    SYSTEM_THEME_NAME,
    THEMES,
    Theme,
    apply_theme,
    get_theme,
    list_themes,
    load_and_apply_theme,
    offer_modern_theme,
    theme_label,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Registry contents
# ---------------------------------------------------------------------------


def test_default_theme_is_registered():
    assert DEFAULT_THEME_NAME in THEMES


def test_the_system_theme_has_no_stylesheet_and_no_colours():
    system = get_theme(SYSTEM_THEME_NAME)
    assert system.stylesheet == "" and system.colours is None


def test_the_default_theme_is_modern_dark():
    default = get_theme(DEFAULT_THEME_NAME)
    assert default.name == "modern_dark"
    assert default.stylesheet and default.colours is not None


def test_modern_themes_come_first_in_the_list():
    assert [t.name for t in list_themes()][:3] == ["modern_dark", "modern_light", "default"]


def test_themes_have_unique_names():
    names = [t.name for t in list_themes()]
    assert len(names) == len(set(names))


def test_themes_have_human_labels():
    for theme in list_themes():
        assert theme.label
        assert isinstance(theme, Theme)


def test_known_theme_names_are_present():
    expected = {"default", "dracula", "nord", "solarized_dark", "solarized_light",
                "modern_dark", "modern_light"}
    assert expected.issubset(set(THEMES.keys()))


# ---------------------------------------------------------------------------
# get_theme
# ---------------------------------------------------------------------------


def test_get_theme_returns_default_for_unknown_name():
    out = get_theme("not-a-theme")
    assert out.name == DEFAULT_THEME_NAME


def test_get_theme_round_trips_known_name():
    assert get_theme("dracula").name == "dracula"


# ---------------------------------------------------------------------------
# apply_theme (Qt)
# ---------------------------------------------------------------------------


def test_apply_theme_returns_actual_name(qapp):
    out = apply_theme(qapp, "dracula")
    assert out == "dracula"


def test_apply_theme_unknown_falls_back(qapp):
    out = apply_theme(qapp, "garbage")
    assert out == DEFAULT_THEME_NAME


def test_apply_theme_sets_stylesheet(qapp):
    apply_theme(qapp, "nord")
    # Some non-empty QSS got applied
    assert qapp.styleSheet()


def test_apply_default_clears_stylesheet(qapp):
    apply_theme(qapp, "dracula")
    assert qapp.styleSheet()
    apply_theme(qapp, "default")
    assert qapp.styleSheet() == ""


@pytest.mark.parametrize("name", ["modern_dark", "modern_light"])
def test_a_modern_theme_sets_fusion_and_its_palette(qapp, monkeypatch, name):
    from PySide6.QtGui import QPalette
    styles = []
    monkeypatch.setattr(qapp, "setStyle", lambda style: styles.append(style))
    apply_theme(qapp, name)
    colours = get_theme(name).colours
    assert styles == ["Fusion"]
    palette = qapp.palette()
    assert palette.color(QPalette.ColorRole.Window).name() == colours.window
    assert palette.color(QPalette.ColorRole.Highlight).name() == colours.accent
    assert qapp.styleSheet() == get_theme(name).stylesheet


def test_the_system_theme_puts_the_native_style_and_palette_back(qapp):
    from PySide6.QtGui import QPalette
    native_style = qapp.style().objectName()
    native_window = qapp.palette().color(QPalette.ColorRole.Window).name()
    apply_theme(qapp, "modern_dark")
    apply_theme(qapp, "modern_light")       # the native look is kept across modern themes
    apply_theme(qapp, SYSTEM_THEME_NAME)
    assert native_style                      # read before any stylesheet hid it
    assert qapp.style().objectName() == native_style
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == native_window
    assert qapp.styleSheet() == ""


def test_a_stylesheet_only_theme_after_a_modern_one_drops_the_palette(qapp):
    from PySide6.QtGui import QPalette
    native_window = qapp.palette().color(QPalette.ColorRole.Window).name()
    apply_theme(qapp, "modern_dark")
    apply_theme(qapp, "nord")
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == native_window
    assert qapp.styleSheet() == get_theme("nord").stylesheet


# ---------------------------------------------------------------------------
# theme_label
# ---------------------------------------------------------------------------


def test_theme_label_is_translated_when_the_theme_has_a_key(monkeypatch):
    from Imervue.multi_language.language_wrapper import language_wrapper
    monkeypatch.setattr(language_wrapper, "language_word_dict",
                        {"theme_modern_dark": "現代深色"})
    assert theme_label(get_theme("modern_dark")) == "現代深色"
    assert theme_label(get_theme("modern_light")) == "Modern Light"   # key not translated
    assert theme_label(get_theme("nord")) == "Nord"                   # a proper name


# ---------------------------------------------------------------------------
# offer_modern_theme
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("before", "after", "changed"), [
    ({}, "modern_dark", True),                       # never opened Preferences
    ({"theme": "default"}, "modern_dark", True),     # stored on every OK, not a choice
    ({"theme": "nord"}, "nord", False),              # a real choice stays
    ({"theme": "default", MODERN_OFFERED_KEY: True}, "default", False),   # chosen since
])
def test_offer_modern_theme(before, after, changed):
    settings = dict(before)
    assert offer_modern_theme(settings) is changed
    assert settings.get("theme", "modern_dark") == after
    assert settings[MODERN_OFFERED_KEY] is True


def test_the_offer_is_made_once(qapp):
    user_setting_dict.pop(MODERN_OFFERED_KEY, None)
    user_setting_dict["theme"] = SYSTEM_THEME_NAME
    assert load_and_apply_theme(qapp) == "modern_dark"
    user_setting_dict["theme"] = SYSTEM_THEME_NAME     # picked in Preferences afterwards
    assert load_and_apply_theme(qapp) == SYSTEM_THEME_NAME


# ---------------------------------------------------------------------------
# load_and_apply_theme
# ---------------------------------------------------------------------------


def test_load_and_apply_uses_user_setting(qapp):
    user_setting_dict["theme"] = "solarized_dark"
    out = load_and_apply_theme(qapp)
    assert out == "solarized_dark"


def test_load_and_apply_handles_missing_setting(qapp):
    user_setting_dict.pop("theme", None)
    out = load_and_apply_theme(qapp)
    assert out == DEFAULT_THEME_NAME


def test_load_and_apply_handles_garbage_setting(qapp):
    user_setting_dict["theme"] = "🚫"
    out = load_and_apply_theme(qapp)
    assert out == DEFAULT_THEME_NAME


# ---------------------------------------------------------------------------
# Preferences dialog wiring
# ---------------------------------------------------------------------------


def test_preferences_dialog_persists_theme(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict["theme"] = DEFAULT_THEME_NAME
    dlg = PreferencesDialog()
    # Programmatically pick "nord"
    for i in range(dlg._theme_combo.count()):
        if dlg._theme_combo.itemData(i) == "nord":
            dlg._theme_combo.setCurrentIndex(i)
            break
    dlg._accept()
    assert user_setting_dict["theme"] == "nord"


def test_preferences_dialog_combo_populated(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    dlg = PreferencesDialog()
    assert dlg._theme_combo.count() == len(THEMES)


def test_preferences_dialog_preselects_the_default_for_a_new_profile(qapp):
    from Imervue.gui.preferences_dialog import PreferencesDialog
    user_setting_dict.pop("theme", None)
    dlg = PreferencesDialog()
    assert dlg._theme_combo.currentData() == DEFAULT_THEME_NAME
    assert dlg._theme_combo.currentText() == "Modern Dark"


@pytest.fixture(autouse=True)
def _reset_stylesheet(qapp):
    """Don't leak a styled QApplication into other tests."""
    yield
    apply_theme(qapp, SYSTEM_THEME_NAME)
