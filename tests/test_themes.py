"""Tests for the theme registry and apply pipeline."""
from __future__ import annotations

import pytest

from Imervue.system.themes import (
    DEFAULT_THEME_NAME,
    THEMES,
    Theme,
    apply_theme,
    get_theme,
    list_themes,
    load_and_apply_theme,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


# ---------------------------------------------------------------------------
# Registry contents
# ---------------------------------------------------------------------------


def test_default_theme_is_registered():
    assert DEFAULT_THEME_NAME in THEMES


def test_default_theme_has_empty_stylesheet():
    assert get_theme(DEFAULT_THEME_NAME).stylesheet == ""


def test_themes_have_unique_names():
    names = [t.name for t in list_themes()]
    assert len(names) == len(set(names))


def test_themes_have_human_labels():
    for theme in list_themes():
        assert theme.label
        assert isinstance(theme, Theme)


def test_known_theme_names_are_present():
    expected = {"default", "dracula", "nord", "solarized_dark", "solarized_light"}
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


@pytest.fixture(autouse=True)
def _reset_stylesheet(qapp):
    """Don't leak a styled QApplication into other tests."""
    yield
    apply_theme(qapp, DEFAULT_THEME_NAME)
