"""Tests for the shortcut registry + dialog."""
from __future__ import annotations

import pytest

from Imervue.paint.shortcut_registry import (
    DEFAULT_SHORTCUTS,
    ShortcutEntry,
    ShortcutRegistry,
)


# ---------------------------------------------------------------------------
# Defaults catalogue
# ---------------------------------------------------------------------------


def test_default_set_includes_core_paint_actions():
    ids = {entry.action_id for entry in DEFAULT_SHORTCUTS}
    assert {
        "paint.tool.brush", "paint.tool.eraser", "paint.tool.eyedropper",
        "paint.layer.add", "paint.edit.undo",
    } <= ids


def test_default_action_ids_are_unique():
    ids = [entry.action_id for entry in DEFAULT_SHORTCUTS]
    assert len(ids) == len(set(ids))


def test_default_keys_are_non_empty():
    for entry in DEFAULT_SHORTCUTS:
        assert entry.default_key.strip(), entry.action_id


# ---------------------------------------------------------------------------
# Registry construction
# ---------------------------------------------------------------------------


def test_with_defaults_loads_every_action():
    registry = ShortcutRegistry.with_defaults()
    for entry in DEFAULT_SHORTCUTS:
        assert registry.get(entry.action_id) == entry.default_key


def test_post_init_drops_unknown_action_ids():
    """A user_setting_dict shipped from an older build that names an
    action the current code doesn't know about must not poison the
    registry."""
    raw = {entry.action_id: entry.default_key for entry in DEFAULT_SHORTCUTS}
    raw["paint.deprecated.flux"] = "Ctrl+W"
    registry = ShortcutRegistry(_bindings=raw)
    assert "paint.deprecated.flux" not in registry.to_dict()


def test_post_init_backfills_missing_actions():
    """A partial registry must be filled out so callers can iterate
    every documented action without KeyError."""
    registry = ShortcutRegistry(_bindings={})
    assert registry.get("paint.tool.brush") == "B"


# ---------------------------------------------------------------------------
# get / set / reset
# ---------------------------------------------------------------------------


def test_get_returns_current_binding():
    registry = ShortcutRegistry.with_defaults()
    assert registry.get("paint.tool.brush") == "B"


def test_get_unknown_raises():
    registry = ShortcutRegistry.with_defaults()
    with pytest.raises(KeyError):
        registry.get("paint.missing.tool")


def test_set_changes_binding_and_returns_true():
    registry = ShortcutRegistry.with_defaults()
    assert registry.set("paint.tool.brush", "Shift+B") is True
    assert registry.get("paint.tool.brush") == "Shift+B"


def test_set_idempotent_returns_false():
    registry = ShortcutRegistry.with_defaults()
    assert registry.set("paint.tool.brush", "B") is False


def test_set_rejects_empty_key():
    registry = ShortcutRegistry.with_defaults()
    with pytest.raises(ValueError, match="non-empty"):
        registry.set("paint.tool.brush", "   ")


def test_set_unknown_action_raises():
    registry = ShortcutRegistry.with_defaults()
    with pytest.raises(KeyError):
        registry.set("paint.missing.tool", "Q")


def test_set_strips_whitespace():
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.brush", "  Shift+B  ")
    assert registry.get("paint.tool.brush") == "Shift+B"


def test_reset_restores_documented_default():
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.brush", "Q")
    assert registry.reset("paint.tool.brush") is True
    assert registry.get("paint.tool.brush") == "B"


def test_reset_unknown_action_raises():
    registry = ShortcutRegistry.with_defaults()
    with pytest.raises(KeyError):
        registry.reset("paint.missing.tool")


def test_reset_all_returns_every_default():
    registry = ShortcutRegistry.with_defaults()
    for entry in DEFAULT_SHORTCUTS:
        registry.set(entry.action_id, "Ctrl+Alt+Z")
    registry.reset_all()
    for entry in DEFAULT_SHORTCUTS:
        assert registry.get(entry.action_id) == entry.default_key


# ---------------------------------------------------------------------------
# items() preserves the documented order
# ---------------------------------------------------------------------------


def test_items_orders_by_default_catalogue():
    registry = ShortcutRegistry.with_defaults()
    item_ids = [pair[0] for pair in registry.items()]
    expected = [entry.action_id for entry in DEFAULT_SHORTCUTS]
    assert item_ids == expected


# ---------------------------------------------------------------------------
# conflicts
# ---------------------------------------------------------------------------


def test_conflicts_finds_other_action_with_same_key():
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.brush", "Z")  # collides with paint.tool.zoom
    colliding = registry.conflicts("paint.tool.brush", "Z")
    assert "paint.tool.zoom" in colliding


def test_conflicts_excludes_querying_action():
    registry = ShortcutRegistry.with_defaults()
    # The querying action's own binding never appears in its conflict list.
    colliding = registry.conflicts("paint.tool.zoom", "Z")
    assert "paint.tool.zoom" not in colliding


def test_conflicts_returns_empty_when_unique():
    registry = ShortcutRegistry.with_defaults()
    colliding = registry.conflicts("paint.tool.brush", "Ctrl+Alt+Q")
    assert colliding == []


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


def test_to_dict_round_trip_preserves_overrides():
    original = ShortcutRegistry.with_defaults()
    original.set("paint.tool.brush", "Shift+B")
    rebuilt = ShortcutRegistry.from_dict(original.to_dict())
    assert rebuilt.get("paint.tool.brush") == "Shift+B"


def test_from_dict_handles_non_dict_input():
    rebuilt = ShortcutRegistry.from_dict(None)
    # Falls back to defaults.
    assert rebuilt.get("paint.tool.brush") == "B"


def test_from_dict_drops_non_string_values():
    rebuilt = ShortcutRegistry.from_dict({
        "paint.tool.brush": 42,
        "paint.tool.eraser": "Shift+E",
    })
    # Brush kept the default; eraser took the override.
    assert rebuilt.get("paint.tool.brush") == "B"
    assert rebuilt.get("paint.tool.eraser") == "Shift+E"


def test_from_dict_drops_blank_string_values():
    rebuilt = ShortcutRegistry.from_dict({"paint.tool.brush": "   "})
    assert rebuilt.get("paint.tool.brush") == "B"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def test_save_load_round_trip_via_user_setting_dict():
    from Imervue.paint.shortcut_registry import load_shortcuts, save_shortcuts
    registry = ShortcutRegistry.with_defaults()
    registry.set("paint.tool.brush", "Ctrl+Q")
    save_shortcuts(registry)
    rebuilt = load_shortcuts()
    assert rebuilt.get("paint.tool.brush") == "Ctrl+Q"


# ---------------------------------------------------------------------------
# ShortcutEntry frozen invariants
# ---------------------------------------------------------------------------


def test_entry_is_frozen():
    entry = ShortcutEntry("x", "y", "Z")
    with pytest.raises((AttributeError, TypeError)):
        entry.action_id = "other"


# ---------------------------------------------------------------------------
# Dialog smoke tests
# ---------------------------------------------------------------------------


def test_dialog_opens_with_default_registry(qapp):
    from Imervue.paint.shortcut_dialog import ShortcutDialog
    dialog = ShortcutDialog()
    try:
        assert dialog.registry().get("paint.tool.brush") == "B"
    finally:
        dialog.deleteLater()


def test_dialog_changes_dont_mutate_input_registry(qapp):
    """The dialog must operate on a copy so a Cancel returns the
    caller's registry untouched."""
    from Imervue.paint.shortcut_dialog import ShortcutDialog
    original = ShortcutRegistry.with_defaults()
    dialog = ShortcutDialog(registry=original)
    try:
        dialog.registry().set("paint.tool.brush", "Q")
        # Original is unchanged because the dialog kept a copy.
        assert original.get("paint.tool.brush") == "B"
    finally:
        dialog.deleteLater()


def test_dialog_reset_all_restores_defaults_in_working_copy(qapp):
    from Imervue.paint.shortcut_dialog import ShortcutDialog
    dialog = ShortcutDialog()
    try:
        dialog.registry().set("paint.tool.brush", "Q")
        dialog._on_reset_all()  # noqa: SLF001
        assert dialog.registry().get("paint.tool.brush") == "B"
    finally:
        dialog.deleteLater()
