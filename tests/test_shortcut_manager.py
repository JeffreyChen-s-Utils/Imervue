"""
Tests for the ShortcutManager — keybinding persistence and lookup.

Imports PySide6 for Qt.Key enums; requires the ``qapp`` fixture.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from Imervue.gui.shortcut_settings_dialog import (
    DEFAULT_SHORTCUTS,
    ACTION_DISPLAY_KEYS,
    ACTION_FALLBACKS,
    ShortcutManager,
    _k,
)


# ---------------------------------------------------------------------------
# _k helper
# ---------------------------------------------------------------------------

class TestKHelper:
    def test_extracts_value_from_enum(self):
        result = _k(Qt.Key.Key_A)
        assert isinstance(result, int)
        assert result == Qt.Key.Key_A.value

    def test_extracts_int_from_raw_int(self):
        result = _k(65)
        assert result == 65


# ---------------------------------------------------------------------------
# Default shortcuts consistency
# ---------------------------------------------------------------------------

class TestDefaultShortcuts:
    def test_all_actions_have_display_keys(self):
        for action_id in DEFAULT_SHORTCUTS:
            assert action_id in ACTION_DISPLAY_KEYS, (
                f"Action '{action_id}' missing from ACTION_DISPLAY_KEYS"
            )

    def test_all_actions_have_fallbacks(self):
        for action_id in DEFAULT_SHORTCUTS:
            assert action_id in ACTION_FALLBACKS, (
                f"Action '{action_id}' missing from ACTION_FALLBACKS"
            )

    def test_all_shortcuts_are_int_tuples(self):
        for action_id, (key, mods) in DEFAULT_SHORTCUTS.items():
            assert isinstance(key, int), f"{action_id} key is not int: {type(key)}"
            assert isinstance(mods, int), f"{action_id} mods is not int: {type(mods)}"

    def test_no_duplicate_key_combos(self):
        combos = list(DEFAULT_SHORTCUTS.values())
        unique = set(combos)
        assert len(combos) == len(unique), "Duplicate key combos in DEFAULT_SHORTCUTS"


# ---------------------------------------------------------------------------
# ShortcutManager
# ---------------------------------------------------------------------------

class TestShortcutManager:
    @pytest.fixture
    def manager(self, qapp):
        m = ShortcutManager()
        m._action_to_key = dict(DEFAULT_SHORTCUTS)
        m._rebuild_reverse()
        return m

    def test_get_action_known_key(self, manager):
        # Ctrl+Z should be "undo"
        ctrl = Qt.KeyboardModifier.ControlModifier.value
        z = _k(Qt.Key.Key_Z)
        action = manager.get_action(z, ctrl)
        assert action == "undo"

    def test_get_action_unknown_key(self, manager):
        assert manager.get_action(999999, 0) is None

    def test_get_key_known_action(self, manager):
        key, mods = manager.get_key("undo")
        assert key == _k(Qt.Key.Key_Z)
        assert mods == Qt.KeyboardModifier.ControlModifier.value

    def test_get_key_unknown_action(self, manager):
        assert manager.get_key("nonexistent") == (0, 0)

    def test_set_key_updates_mapping(self, manager):
        new_key = _k(Qt.Key.Key_X)
        manager.set_key("undo", new_key, 0)
        assert manager.get_key("undo") == (new_key, 0)
        assert manager.get_action(new_key, 0) == "undo"

    def test_set_key_reverse_lookup_updated(self, manager):
        """After remapping, old combo should no longer resolve."""
        old_key, old_mods = manager.get_key("undo")
        new_key = _k(Qt.Key.Key_X)
        manager.set_key("undo", new_key, 0)
        # Old combo no longer maps to undo
        assert manager.get_action(old_key, old_mods) != "undo"

    def test_reset_to_defaults(self, manager):
        manager.set_key("undo", 999, 0)
        manager.reset_to_defaults()
        key, mods = manager.get_key("undo")
        assert (key, mods) == DEFAULT_SHORTCUTS["undo"]

    def test_modifier_masking(self, manager):
        """get_action should mask out KeypadModifier and other noise."""
        ctrl = Qt.KeyboardModifier.ControlModifier.value
        keypad = Qt.KeyboardModifier.KeypadModifier.value
        z = _k(Qt.Key.Key_Z)
        # With extra KeypadModifier, should still find undo
        action = manager.get_action(z, ctrl | keypad)
        assert action == "undo"

    def test_key_to_string(self, manager):
        s = ShortcutManager.key_to_string(_k(Qt.Key.Key_Z),
                                           Qt.KeyboardModifier.ControlModifier.value)
        assert isinstance(s, str)
        assert len(s) > 0

    def test_key_to_string_empty_for_zero(self, manager):
        assert ShortcutManager.key_to_string(0, 0) == ""


# ---------------------------------------------------------------------------
# Save / Load round-trip
# ---------------------------------------------------------------------------

class TestShortcutPersistence:
    def test_save_and_load(self, qapp):
        """Manager should persist custom mappings and reload them."""
        from Imervue.user_settings.user_setting_dict import user_setting_dict

        m1 = ShortcutManager()
        custom_key = _k(Qt.Key.Key_Q)
        m1.set_key("undo", custom_key, 0)
        m1.save()

        # Verify it was written to user settings
        saved = user_setting_dict.get("keyboard_shortcuts")
        assert saved is not None
        assert saved["undo"] == [custom_key, 0]

        # Load into a new manager
        m2 = ShortcutManager()
        m2.load()
        assert m2.get_key("undo") == (custom_key, 0)
