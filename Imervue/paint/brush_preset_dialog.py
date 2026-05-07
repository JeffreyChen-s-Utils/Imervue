"""Custom brush preset manager dialog.

Surfaces the per-tool sub-tool registry that ``ToolState`` already
maintains. The user picks a preset and clicks **Apply** to swap the
live brush + fill settings with the snapshot, **Save** to capture
the current settings under a new name (or overwrite an existing
one), **Delete** to drop a preset, and **Rename** to relabel it.

The dialog is purely a UI shell — every mutation goes through the
public ``ToolState`` API so persistence + event propagation stay on
a single code path. Listeners (BrushDock, FillDock) see EVENT_BRUSH /
EVENT_FILL fire on apply and refresh themselves.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts

if TYPE_CHECKING:
    from Imervue.paint.tool_state import ToolState


class BrushPresetDialog(QDialog):
    """List + edit the active tool's saved sub-tool presets."""

    def __init__(self, state: ToolState, parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_brush_presets_title", "Brush presets"),
        )
        self.setMinimumWidth(360)
        self._state = state

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        self._refresh_list()

        save_btn = QPushButton(
            lang.get("paint_brush_presets_save", "Save current"),
        )
        save_btn.clicked.connect(self._on_save)
        apply_btn = QPushButton(
            lang.get("paint_brush_presets_apply", "Apply"),
        )
        apply_btn.clicked.connect(self._on_apply)
        rename_btn = QPushButton(
            lang.get("paint_brush_presets_rename", "Rename"),
        )
        rename_btn.clicked.connect(self._on_rename)
        delete_btn = QPushButton(
            lang.get("paint_brush_presets_delete", "Delete"),
        )
        delete_btn.clicked.connect(self._on_delete)

        button_row = QHBoxLayout()
        for btn in (save_btn, apply_btn, rename_btn, delete_btn):
            button_row.addWidget(btn)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        close_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                lang.get(
                    "paint_brush_presets_hint",
                    "Saved presets for the active tool. Double-click to apply.",
                ),
            ),
        )
        layout.addWidget(self._list, 1)
        layout.addLayout(button_row)
        layout.addWidget(close_box)

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for sub in self._state.list_sub_tools(self._state.tool):
            item = QListWidgetItem(sub.name)
            item.setData(Qt.ItemDataRole.UserRole, sub.name)
            self._list.addItem(item)
        self._list.blockSignals(False)

    # ---- button handlers ---------------------------------------------------

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def _on_save(self) -> None:
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("paint_brush_presets_save_title", "Save preset"),
            lang.get("paint_brush_presets_save_label", "Preset name:"),
            text=self._suggest_name(),
        )
        if not ok:
            return
        name = str(name).strip()
        if not name:
            return
        if len(name) > ts.SUB_TOOL_NAME_MAX_LEN:
            QMessageBox.warning(
                self,
                lang.get("paint_brush_presets_save_title", "Save preset"),
                lang.get(
                    "paint_brush_presets_too_long",
                    "Preset name is too long.",
                ),
            )
            return
        self._state.add_sub_tool(self._state.tool, name)
        self._refresh_list()
        self._select_by_name(name)

    def _on_apply(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        self._state.apply_sub_tool(self._state.tool, name)

    def _on_rename(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        lang = language_wrapper.language_word_dict
        new_name, ok = QInputDialog.getText(
            self,
            lang.get("paint_brush_presets_rename_title", "Rename preset"),
            lang.get("paint_brush_presets_rename_label", "New name:"),
            text=name,
        )
        if not ok:
            return
        new_name = str(new_name).strip()
        if not new_name or new_name == name:
            return
        # No native rename verb; mirror the snapshot under the new name
        # then drop the old. Re-uses the existing settings exactly.
        existing = next(
            (s for s in self._state.list_sub_tools(self._state.tool)
             if s.name == name),
            None,
        )
        if existing is None:
            return
        # Stash live settings, write the existing snapshot under the
        # new name, then restore live settings — so the rename does
        # not perturb the user's current brush.
        live_brush = self._state.brush
        live_fill = self._state.fill
        self._state.brush = existing.brush
        self._state.fill = existing.fill
        self._state.add_sub_tool(self._state.tool, new_name)
        self._state.brush = live_brush
        self._state.fill = live_fill
        self._state.remove_sub_tool(self._state.tool, name)
        self._refresh_list()
        self._select_by_name(new_name)

    def _on_delete(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        self._state.remove_sub_tool(self._state.tool, name)
        self._refresh_list()

    def _on_double_clicked(self, _item: QListWidgetItem) -> None:
        self._on_apply()

    # ---- helpers -----------------------------------------------------------

    def _suggest_name(self) -> str:
        existing = {
            s.name for s in self._state.list_sub_tools(self._state.tool)
        }
        i = 1
        while True:
            candidate = f"Preset {i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _select_by_name(self, name: str) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole)) == name:
                self._list.setCurrentRow(row)
                return


def open_brush_preset_dialog(state: ToolState, parent=None) -> None:
    dlg = BrushPresetDialog(state, parent=parent)
    dlg.exec()
