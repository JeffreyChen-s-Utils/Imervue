"""Tests for the Preferences dialog — Phase 34d.

Covers:

* ``restore_defaults`` resets every widget to the documented baseline.
* Cancel after Restore Defaults persists nothing (transactional).
* OK persists every value through ``user_setting_dict``.
"""
from __future__ import annotations

import pytest

from Imervue.gui.preferences_dialog import (
    UI_SCALE_DEFAULT_PERCENT,
    VRAM_DEFAULT_MB,
    PreferencesDialog,
)
from Imervue.system.themes import DEFAULT_THEME_NAME
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _reset_user_settings():
    """Strip every key the dialog touches before and after each test
    so the tests are independent."""
    keys = ("vram_limit_auto", "vram_limit_mb", "ui_scale_percent", "theme")
    for k in keys:
        user_setting_dict.pop(k, None)
    yield
    for k in keys:
        user_setting_dict.pop(k, None)


def test_restore_defaults_resets_every_field(qapp):
    user_setting_dict["vram_limit_auto"] = False
    user_setting_dict["vram_limit_mb"] = 4096
    user_setting_dict["ui_scale_percent"] = 175
    user_setting_dict["theme"] = "anything-else"
    dlg = PreferencesDialog()
    try:
        dlg.restore_defaults()
        assert dlg._auto_vram.isChecked()           # noqa: SLF001
        assert dlg._vram_spin.value() == VRAM_DEFAULT_MB    # noqa: SLF001
        assert not dlg._vram_spin.isEnabled()       # noqa: SLF001
        assert dlg._ui_scale_spin.value() == UI_SCALE_DEFAULT_PERCENT   # noqa: SLF001
        assert dlg._theme_combo.currentData() == DEFAULT_THEME_NAME     # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_restore_defaults_then_cancel_persists_nothing(qapp):
    """Hitting Restore Defaults is purely cosmetic until OK confirms it.
    The dialog must therefore not write to ``user_setting_dict`` until
    the user clicks OK — Cancel after Restore should leave existing
    values intact on disk."""
    user_setting_dict["vram_limit_auto"] = False
    user_setting_dict["vram_limit_mb"] = 4096
    dlg = PreferencesDialog()
    try:
        dlg.restore_defaults()
        dlg.reject()
        # The original (non-default) values should still be in place —
        # restore_defaults touched the widgets, but reject discarded the form.
        assert user_setting_dict["vram_limit_auto"] is False
        assert user_setting_dict["vram_limit_mb"] == 4096
    finally:
        dlg.deleteLater()


def test_accept_persists_every_field(qapp):
    dlg = PreferencesDialog()
    try:
        dlg._auto_vram.setChecked(False)            # noqa: SLF001
        dlg._vram_spin.setValue(2048)               # noqa: SLF001
        dlg._ui_scale_spin.setValue(125)            # noqa: SLF001
        dlg._theme_combo.setCurrentIndex(0)         # noqa: SLF001
        dlg._accept()                               # noqa: SLF001
        assert user_setting_dict["vram_limit_auto"] is False
        assert user_setting_dict["vram_limit_mb"] == 2048
        assert user_setting_dict["ui_scale_percent"] == 125
        assert user_setting_dict["theme"] == dlg._theme_combo.itemData(0)   # noqa: SLF001
    finally:
        dlg.deleteLater()


def test_button_box_includes_restore_defaults(qapp):
    """Sanity check: the standard-button enum includes RestoreDefaults
    so the user has a discoverable trigger for the new method."""
    from PySide6.QtWidgets import QDialogButtonBox
    dlg = PreferencesDialog()
    try:
        # Find the embedded QDialogButtonBox — Qt names it the only
        # one in the dialog so a class-based query is safe.
        boxes = dlg.findChildren(QDialogButtonBox)
        assert boxes
        button = boxes[0].button(QDialogButtonBox.StandardButton.RestoreDefaults)
        assert button is not None
    finally:
        dlg.deleteLater()
