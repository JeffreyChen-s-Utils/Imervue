"""Workspace presets dialog — save, load, rename, and delete layouts.

The dialog captures a snapshot of the main window (geometry, dock state,
root folder, splitter sizes) and stores it as a named preset. Users can
flip between "Browse", "Develop", "Export" layouts without re-arranging
panels every time — the same ergonomic hook you'd find in Lightroom's
Workspaces or Bridge's layouts.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.gui.workspace_manager import (
    Workspace,
    decode_bytes,
    encode_bytes,
    workspace_manager,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.workspace_dialog")


def capture_current_workspace(ui: ImervueMainWindow, name: str) -> Workspace:
    """Snapshot the live main-window layout into a :class:`Workspace`."""
    splitter_sizes: list[int] = []
    splitter = getattr(ui, "_main_splitter", None)
    if splitter is not None:
        splitter_sizes = list(splitter.sizes())
    root_folder = ""
    tree_model = getattr(ui.tree, "model", lambda: None)()
    root_index = ui.tree.rootIndex() if hasattr(ui, "tree") else None
    if tree_model is not None and root_index is not None and root_index.isValid():
        root_folder = tree_model.filePath(root_index) or ""
    return Workspace(
        name=name,
        geometry_b64=encode_bytes(bytes(ui.saveGeometry())),
        state_b64=encode_bytes(bytes(ui.saveState())),
        maximized=ui.isMaximized(),
        root_folder=root_folder,
        splitter_sizes=splitter_sizes,
    )


def apply_workspace(ui: ImervueMainWindow, workspace: Workspace) -> None:
    """Restore the main window to *workspace* — geometry, layout, folder."""
    geometry = decode_bytes(workspace.geometry_b64)
    state = decode_bytes(workspace.state_b64)
    if geometry:
        ui.restoreGeometry(QByteArray(geometry))
    if state:
        ui.restoreState(QByteArray(state))
    if workspace.maximized:
        ui.showMaximized()
    else:
        ui.showNormal()
    splitter = getattr(ui, "_main_splitter", None)
    if splitter is not None and workspace.splitter_sizes:
        splitter.setSizes(workspace.splitter_sizes)
    if workspace.root_folder:
        tree_model = getattr(ui.tree, "model", lambda: None)()
        if tree_model is not None:
            tree_model.setRootPath(workspace.root_folder)
            ui.tree.setRootIndex(tree_model.index(workspace.root_folder))


class WorkspaceDialog(QDialog):
    """List-and-buttons UI for managing named workspace presets."""

    def __init__(self, ui: ImervueMainWindow) -> None:
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("workspace_title", "Workspaces"))
        self.setMinimumSize(420, 320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get(
                "workspace_explain",
                "Save the current window layout as a named preset and jump "
                "between layouts without rearranging panels.",
            ),
        ))

        self._list = QListWidget()
        self._list.setSelectionMode(self._list.SelectionMode.SingleSelection)
        self._list.itemDoubleClicked.connect(lambda _it: self._load_selected())
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        self._btn_save = QPushButton(lang.get("workspace_save", "Save Current"))
        self._btn_save.clicked.connect(self._save_current)
        btn_row.addWidget(self._btn_save)

        self._btn_load = QPushButton(lang.get("workspace_load", "Load"))
        self._btn_load.clicked.connect(self._load_selected)
        btn_row.addWidget(self._btn_load)

        self._btn_rename = QPushButton(lang.get("workspace_rename", "Rename"))
        self._btn_rename.clicked.connect(self._rename_selected)
        btn_row.addWidget(self._btn_rename)

        self._btn_delete = QPushButton(lang.get("workspace_delete", "Delete"))
        self._btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self._btn_delete)

        layout.addLayout(btn_row)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

        self._refresh()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        for ws in workspace_manager.list_all():
            item = QListWidgetItem(ws.name)
            item.setData(Qt.ItemDataRole.UserRole, ws.name)
            self._list.addItem(item)

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _prompt_name(self, title_key: str, title_fallback: str, initial: str = "") -> str | None:
        lang = language_wrapper.language_word_dict
        text, ok = QInputDialog.getText(
            self,
            lang.get(title_key, title_fallback),
            lang.get("workspace_name_label", "Name:"),
            text=initial,
        )
        if not ok:
            return None
        name = text.strip()
        if not name:
            return None
        return name

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _save_current(self) -> None:
        lang = language_wrapper.language_word_dict
        name = self._prompt_name("workspace_save", "Save Current")
        if name is None:
            return
        existing = workspace_manager.get(name)
        if existing is not None:
            reply = QMessageBox.question(
                self,
                lang.get("workspace_overwrite_title", "Overwrite workspace?"),
                lang.get(
                    "workspace_overwrite_msg",
                    "A workspace named '{name}' already exists. Overwrite it?",
                ).format(name=name),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        workspace = capture_current_workspace(self._ui, name)
        workspace_manager.save(workspace)
        self._refresh()

    def _load_selected(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        workspace = workspace_manager.get(name)
        if workspace is None:
            self._refresh()
            return
        apply_workspace(self._ui, workspace)

    def _rename_selected(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        new_name = self._prompt_name("workspace_rename", "Rename", initial=name)
        if new_name is None or new_name == name:
            return
        if not workspace_manager.rename(name, new_name):
            lang = language_wrapper.language_word_dict
            QMessageBox.warning(
                self,
                lang.get("workspace_rename", "Rename"),
                lang.get(
                    "workspace_rename_conflict",
                    "Cannot rename — a workspace named '{name}' already exists.",
                ).format(name=new_name),
            )
            return
        self._refresh()

    def _delete_selected(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        lang = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self,
            lang.get("workspace_delete", "Delete"),
            lang.get(
                "workspace_delete_confirm",
                "Delete workspace '{name}'?",
            ).format(name=name),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        workspace_manager.delete(name)
        self._refresh()


def open_workspace_dialog(ui: ImervueMainWindow) -> None:
    """Open the workspaces dialog as a modal child of *ui*."""
    dlg = WorkspaceDialog(ui)
    dlg.exec()
