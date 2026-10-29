"""Desktop Pet tab — the Global hotkeys group.

The saved-binding merge and shared-key warning helpers, the group builder and
its slots: enabling the OS-level listener and refusing an edited key another
action already uses.
"""
from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QKeySequenceEdit,
    QVBoxLayout,
)

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.hotkey_conflicts import clashing_action, find_conflicts
from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_CLICK_THROUGH,
    ACTION_TOGGLE_LOCK,
    ACTION_TOGGLE_VISIBLE,
    DEFAULT_HOTKEY_BINDINGS,
    is_valid_spec,
)
from Imervue.desktop_pet.pet_workspace_toggles import _set_quietly, _tr

# (action, label key, English label) for each row of the Global hotkeys group.
_HOTKEY_ROWS: tuple[tuple[str, str, str], ...] = (
    (ACTION_TOGGLE_VISIBLE, "desktop_pet_hotkey_toggle_visible", "Show / hide pet"),
    (ACTION_TOGGLE_LOCK, "desktop_pet_hotkey_toggle_lock", "Lock / unlock position"),
    (ACTION_TOGGLE_CLICK_THROUGH, "desktop_pet_hotkey_click_through", "Toggle click-through"),
    (ACTION_SPEAK_NOW, "desktop_pet_hotkey_speak_now", "Speak now"),
)


def _hotkey_label(action: str) -> str:
    """The translated row label of the hotkey *action* (the id itself if unknown)."""
    return next((_tr(key, label) for act, key, label in _HOTKEY_ROWS if act == action), action)


def saved_hotkeys() -> dict[str, str]:
    """The pet's key bindings: the defaults, overridden by every saved non-empty spec."""
    persisted = pet_settings.load().get("hotkeys", {}) or {}
    merged = dict(DEFAULT_HOTKEY_BINDINGS)
    if isinstance(persisted, dict):
        merged.update({a: s for a, s in persisted.items() if isinstance(s, str) and s})
    return merged


def hotkey_conflict_notice(bindings: dict[str, str]) -> str:
    """A status-line warning naming the actions that share a key, or "" when none do."""
    clashes = find_conflicts(bindings)
    if not clashes:
        return ""
    template = _tr("desktop_pet_hotkeys_shared",
                   "These hotkeys share one key — change one of them: {pairs}")
    pairs = "; ".join(" / ".join(_hotkey_label(a) for a in actions) for actions in clashes.values())
    return template.format(pairs=pairs)


class PetWorkspaceHotkeysMixin:
    """Global-hotkeys group of :class:`PetWorkspace`."""

    def _build_hotkey_group(self) -> QGroupBox:
        """System-wide keyboard shortcuts. ``pynput`` provides the
        OS-level hook; missing dep degrades the group to a hint
        rather than an error."""
        group = QGroupBox(_tr("desktop_pet_group_hotkeys", "Global hotkeys"))
        layout = QVBoxLayout(group)
        settings = pet_settings.load()
        merged = saved_hotkeys()

        self._hotkey_check = QCheckBox(
            _tr(
                "desktop_pet_hotkeys_enabled",
                "Enable global hotkeys (needs pynput)",
            ),
        )
        self._hotkey_check.setChecked(bool(settings.get("hotkeys_enabled", False)))
        self._hotkey_check.toggled.connect(self._on_hotkeys_toggled)
        layout.addWidget(self._hotkey_check)

        form = QFormLayout()
        self._hotkey_edits: dict[str, QKeySequenceEdit] = {}
        for action, label_key, default_label in _HOTKEY_ROWS:
            edit = QKeySequenceEdit(QKeySequence(merged[action]))
            edit.editingFinished.connect(
                lambda _a=action, _e=edit: self._on_hotkey_edited(_a, _e),
            )
            form.addRow(_tr(label_key, default_label), edit)
            self._hotkey_edits[action] = edit
        layout.addLayout(form)
        return group

    def _on_hotkeys_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_hotkeys_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                _tr(
                    "desktop_pet_hotkeys_missing",
                    "Global hotkeys need pynput — pip install pynput",
                ),
            )
            _set_quietly(self._hotkey_check, False)

    def _on_hotkey_edited(self, action: str, edit: QKeySequenceEdit) -> None:
        """Persist the new binding (if parseable) and refresh the
        running listener so the change takes effect immediately.

        A key another action already uses is refused: the edit goes back to
        the action's current key and the status line names the other action.
        """
        spec = edit.keySequence().toString()
        if not spec or not is_valid_spec(spec):
            return
        bindings = saved_hotkeys()
        clash = clashing_action(bindings, action, spec)
        if clash is not None:
            edit.setKeySequence(QKeySequence(bindings.get(action, "")))
            self._status.setText(_tr(
                "desktop_pet_hotkey_taken",
                "{key} is already the key for “{action}” — kept the previous key",
            ).format(key=spec, action=_hotkey_label(clash)))
            return
        persisted = pet_settings.load().get("hotkeys", {}) or {}
        if not isinstance(persisted, dict):
            persisted = {}
        persisted[action] = spec
        pet_settings.update(hotkeys=persisted)
        self._status.setText(hotkey_conflict_notice(saved_hotkeys()))
        if self._pet_window is not None and self._pet_window.hotkeys_enabled():
            self._pet_window.set_hotkeys_enabled(True)
