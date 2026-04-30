"""Workspace-preset management dialog + verbs.

The :mod:`Imervue.paint.workspace_presets` data model already
ships built-in layouts; what was missing was a UI for the user to
list, save, rename, or delete their own presets. The dialog lists
every available preset (built-in + user) with a button row to
apply, save current, rename, and delete.

The dialog is signal-only: clicking Apply emits
:attr:`apply_requested` with the chosen preset name; the
workspace's Qt layer translates that into the actual dock
re-layout. Saving / renaming / deleting mutate the user-preset
list directly via the :func:`save_workspace_presets` helper.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.workspace_presets import (
    BUILT_IN_PRESETS,
    WorkspacePreset,
    all_workspace_presets,
    load_workspace_presets,
    save_workspace_presets,
)


def add_user_preset(preset: WorkspacePreset) -> None:
    """Append ``preset`` to the user-preset list, replacing same-name.

    Built-in preset names are reserved — re-using one is rejected via
    ``ValueError`` so the user can't accidentally shadow ``Default``.
    """
    if any(b.name == preset.name for b in BUILT_IN_PRESETS):
        raise ValueError(
            f"preset name {preset.name!r} is reserved by a built-in",
        )
    existing = load_workspace_presets()
    rebuilt = [p for p in existing if p.name != preset.name]
    rebuilt.append(preset)
    save_workspace_presets(rebuilt)


def delete_user_preset(name: str) -> bool:
    """Remove a user preset by name. Returns ``True`` if it existed.

    Built-in presets cannot be deleted — calling with a built-in
    name returns ``False`` rather than raising so the dialog button
    can stay generic.
    """
    if any(b.name == name for b in BUILT_IN_PRESETS):
        return False
    existing = load_workspace_presets()
    rebuilt = [p for p in existing if p.name != name]
    if len(rebuilt) == len(existing):
        return False
    save_workspace_presets(rebuilt)
    return True


def rename_user_preset(old_name: str, new_name: str) -> bool:
    """Rename a user preset. Returns ``True`` on success.

    Rejects renames that would collide with a built-in or another
    user preset. Both arguments must be non-empty.
    """
    new_clean = str(new_name).strip()
    if not new_clean:
        raise ValueError("new preset name must be non-empty")
    if any(b.name == new_clean for b in BUILT_IN_PRESETS):
        raise ValueError(
            f"preset name {new_clean!r} is reserved by a built-in",
        )
    existing = load_workspace_presets()
    if not any(p.name == old_name for p in existing):
        return False
    if any(p.name == new_clean for p in existing if p.name != old_name):
        raise ValueError(
            f"preset name {new_clean!r} already exists",
        )
    rebuilt: list[WorkspacePreset] = []
    for preset in existing:
        if preset.name == old_name:
            rebuilt.append(WorkspacePreset(name=new_clean, docks=preset.docks))
        else:
            rebuilt.append(preset)
    save_workspace_presets(rebuilt)
    return True


def is_built_in(name: str) -> bool:
    """Return ``True`` if ``name`` matches a built-in preset."""
    return any(b.name == name for b in BUILT_IN_PRESETS)


class WorkspacePresetDialog(QDialog):
    """Manage workspace layout presets — list + apply / save / delete."""

    apply_requested = Signal(str)        # preset name
    save_requested = Signal(str)         # name to save the current layout under

    def __init__(self, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get(
            "paint_workspace_preset_title", "Workspace Layouts",
        ))
        self.resize(360, 360)

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._refresh_list()
        layout.addWidget(self._list)

        actions = QHBoxLayout()
        apply_btn = QPushButton(lang.get(
            "paint_workspace_preset_apply", "Apply",
        ))
        apply_btn.clicked.connect(self._on_apply)
        actions.addWidget(apply_btn)

        save_btn = QPushButton(lang.get(
            "paint_workspace_preset_save", "Save current…",
        ))
        save_btn.clicked.connect(self._on_save)
        actions.addWidget(save_btn)

        rename_btn = QPushButton(lang.get(
            "paint_workspace_preset_rename", "Rename…",
        ))
        rename_btn.clicked.connect(self._on_rename)
        actions.addWidget(rename_btn)

        delete_btn = QPushButton(lang.get(
            "paint_workspace_preset_delete", "Delete",
        ))
        delete_btn.clicked.connect(self._on_delete)
        actions.addWidget(delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---- public ----------------------------------------------------------

    def selected_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    # ---- internals -------------------------------------------------------

    def _refresh_list(self) -> None:
        lang = language_wrapper.language_word_dict
        self._list.clear()
        for preset in all_workspace_presets():
            tag = lang.get(
                "paint_workspace_preset_built_in", " (built-in)",
            ) if is_built_in(preset.name) else ""
            item = QListWidgetItem(f"{preset.name}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, preset.name)
            self._list.addItem(item)

    def _on_apply(self) -> None:
        name = self.selected_name()
        if name:
            self.apply_requested.emit(name)

    def _on_save(self) -> None:  # pragma: no cover - QInputDialog UI
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("paint_workspace_preset_save", "Save current"),
            lang.get(
                "paint_workspace_preset_save_label",
                "Preset name:",
            ),
        )
        if ok and name.strip():
            self.save_requested.emit(name.strip())
            # The signal handler is responsible for actually
            # building and persisting the WorkspacePreset; refresh
            # the list afterwards so the new entry appears.
            self._refresh_list()

    def _on_rename(self) -> None:  # pragma: no cover - QInputDialog UI
        lang = language_wrapper.language_word_dict
        name = self.selected_name()
        if not name or is_built_in(name):
            return
        new_name, ok = QInputDialog.getText(
            self,
            lang.get("paint_workspace_preset_rename", "Rename preset"),
            lang.get(
                "paint_workspace_preset_rename_label",
                "New name:",
            ),
            text=name,
        )
        if not ok or not new_name.strip():
            return
        try:
            rename_user_preset(name, new_name.strip())
        except ValueError as exc:
            QMessageBox.warning(
                self,
                lang.get("paint_workspace_preset_rename", "Rename preset"),
                str(exc),
            )
        self._refresh_list()

    def _on_delete(self) -> None:
        name = self.selected_name()
        if not name or is_built_in(name):
            return
        delete_user_preset(name)
        self._refresh_list()
