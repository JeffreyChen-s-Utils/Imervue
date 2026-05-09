"""Customisable keyboard-shortcut registry.

A :class:`ShortcutRegistry` maps action ids ("paint.tool.brush") to
key sequences ("B"). The user can override any binding via the
:class:`Imervue.paint.shortcut_dialog.ShortcutDialog` UI; defaults
are baked in here so a fresh install has the conventional bindings
even before the user opens the dialog.

JSON-friendly: the registry persists into
``user_setting_dict["paint_shortcuts"]`` so customisations round-trip
across runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_shortcuts"


@dataclass(frozen=True)
class ShortcutEntry:
    """One row in the registry — action id + label + default key."""

    action_id: str
    label_key: str          # translation key, e.g. ``paint_shortcut_tool_brush``
    default_key: str        # canonical Qt key sequence, e.g. ``"B"`` / ``"Ctrl+S"``


# Default bindings — the conventional set most paint apps share. The
# label keys feed into the multi_language dicts; missing translations
# fall back to the action id.
DEFAULT_SHORTCUTS: tuple[ShortcutEntry, ...] = (
    ShortcutEntry("paint.tool.brush", "paint_shortcut_tool_brush", "B"),
    ShortcutEntry("paint.tool.eraser", "paint_shortcut_tool_eraser", "E"),
    ShortcutEntry("paint.tool.eyedropper", "paint_shortcut_tool_eyedropper", "I"),
    ShortcutEntry("paint.tool.fill", "paint_shortcut_tool_fill", "G"),
    ShortcutEntry("paint.tool.move", "paint_shortcut_tool_move", "V"),
    ShortcutEntry("paint.tool.text", "paint_shortcut_tool_text", "T"),
    ShortcutEntry("paint.tool.gradient", "paint_shortcut_tool_gradient", "U"),
    ShortcutEntry("paint.tool.zoom", "paint_shortcut_tool_zoom", "Z"),
    ShortcutEntry("paint.tool.hand", "paint_shortcut_tool_hand", "H"),
    ShortcutEntry("paint.brush.size_dec", "paint_shortcut_brush_size_dec", "["),
    ShortcutEntry("paint.brush.size_inc", "paint_shortcut_brush_size_inc", "]"),
    ShortcutEntry("paint.layer.add", "paint_shortcut_layer_add", "Ctrl+Shift+N"),
    ShortcutEntry("paint.layer.duplicate", "paint_shortcut_layer_dup", "Ctrl+J"),
    ShortcutEntry("paint.layer.merge_down", "paint_shortcut_layer_merge", "Ctrl+E"),
    ShortcutEntry("paint.layer.move_up", "paint_shortcut_layer_move_up", "Ctrl+]"),
    ShortcutEntry("paint.layer.move_down", "paint_shortcut_layer_move_down", "Ctrl+["),
    ShortcutEntry("paint.edit.undo", "paint_shortcut_undo", "Ctrl+Z"),
    ShortcutEntry("paint.edit.redo", "paint_shortcut_redo", "Ctrl+Shift+Z"),
    ShortcutEntry("paint.edit.deselect", "paint_shortcut_deselect", "Ctrl+D"),
    ShortcutEntry("paint.view.fit", "paint_shortcut_view_fit", "Ctrl+0"),
    ShortcutEntry("paint.view.actual_size", "paint_shortcut_view_actual_size", "Ctrl+1"),
    ShortcutEntry("paint.color.swap", "paint_shortcut_color_swap", "X"),
    ShortcutEntry("paint.color.reset", "paint_shortcut_color_reset", "D"),
)


@dataclass
class ShortcutRegistry:
    """In-memory registry of (action_id → key sequence) bindings."""

    _bindings: dict[str, str] = field(default_factory=dict)

    @classmethod
    def with_defaults(cls) -> ShortcutRegistry:
        return cls(_bindings={
            entry.action_id: entry.default_key
            for entry in DEFAULT_SHORTCUTS
        })

    def __post_init__(self) -> None:
        # Drop entries that don't refer to known action ids — keeps the
        # registry consistent with the current code release even if a
        # user_setting_dict carries entries from an older build.
        valid = {entry.action_id for entry in DEFAULT_SHORTCUTS}
        self._bindings = {
            k: str(v) for k, v in self._bindings.items() if k in valid
        }
        # Backfill any actions that don't have a stored binding yet
        # so callers can iterate the full set.
        for entry in DEFAULT_SHORTCUTS:
            self._bindings.setdefault(entry.action_id, entry.default_key)

    def get(self, action_id: str) -> str:
        """Return the current key sequence for ``action_id``.

        Raises :class:`KeyError` if ``action_id`` isn't in the
        registry — callers shouldn't be querying for unknown actions.
        """
        return self._bindings[action_id]

    def items(self) -> list[tuple[str, str]]:
        """Return ``(action_id, key)`` pairs in :data:`DEFAULT_SHORTCUTS`
        order — the order users expect in the dialog table."""
        return [
            (entry.action_id, self._bindings[entry.action_id])
            for entry in DEFAULT_SHORTCUTS
        ]

    def set(self, action_id: str, key: str) -> bool:
        """Set ``action_id`` to ``key``. Returns ``True`` if it changed.

        ``key`` is normalised to ``str``; callers can pass either a
        QKeySequence string or one this module produced via :meth:`items`.
        Raises :class:`KeyError` for unknown action ids and
        :class:`ValueError` for an empty key.
        """
        if action_id not in self._bindings:
            raise KeyError(action_id)
        normalised = str(key).strip()
        if not normalised:
            raise ValueError("key must be a non-empty sequence")
        if self._bindings[action_id] == normalised:
            return False
        self._bindings[action_id] = normalised
        return True

    def reset(self, action_id: str) -> bool:
        """Restore ``action_id`` to its documented default."""
        for entry in DEFAULT_SHORTCUTS:
            if entry.action_id == action_id:
                return self.set(action_id, entry.default_key)
        raise KeyError(action_id)

    def reset_all(self) -> None:
        for entry in DEFAULT_SHORTCUTS:
            self._bindings[entry.action_id] = entry.default_key

    def conflicts(self, action_id: str, key: str) -> list[str]:
        """Return any other action ids currently bound to the same key.

        Used by the dialog so the user gets a "Ctrl+S is already bound
        to Save" warning before they commit a colliding change.
        """
        normalised = str(key).strip()
        return [
            other_id
            for other_id, other_key in self._bindings.items()
            if other_id != action_id and other_key == normalised
        ]

    def to_dict(self) -> dict:
        return dict(self._bindings)

    @classmethod
    def from_dict(cls, raw: dict | None) -> ShortcutRegistry:
        bindings = {}
        if isinstance(raw, dict):
            valid = {entry.action_id for entry in DEFAULT_SHORTCUTS}
            for key, value in raw.items():
                if key in valid and isinstance(value, str) and value.strip():
                    bindings[key] = value.strip()
        return cls(_bindings=bindings)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_shortcuts() -> ShortcutRegistry:
    """Load the user's customised shortcuts from settings storage."""
    return ShortcutRegistry.from_dict(user_setting_dict.get(_USER_SETTING_KEY))


def save_shortcuts(registry: ShortcutRegistry) -> None:
    """Persist the user's customised shortcuts."""
    user_setting_dict[_USER_SETTING_KEY] = registry.to_dict()
    schedule_save()
