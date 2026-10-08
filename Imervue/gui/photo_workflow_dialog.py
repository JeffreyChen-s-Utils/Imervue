"""Retained photo review: search cohort, comparison, culling, presets and export."""
from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from Imervue.gui.batch_export_dialog import BatchExportDialog
from Imervue.gui.dual_image_view import DualImageView
from Imervue.image import export_presets
from Imervue.image.develop_presets import DevelopPresetStore, apply_recipe_to_paths
from Imervue.image.recipe_store import recipe_store
from Imervue.library import image_index
from Imervue.library.photo_workflow import PhotoWorkflow
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict

logger = logging.getLogger("Imervue.photo_workflow")
PAGE_SIZE = 500


def _word(key: str, fallback: str) -> str:
    return language_wrapper.language_word_dict.get(key, fallback)


class _WorkflowCompare(DualImageView):
    def __init__(self, workflow):
        super().__init__(workflow._ui, max_edge=800)
        self._workflow = workflow

    def _request_step(self, step: int) -> None:
        self._workflow._advance_comparison(step)


class PhotoWorkflowDialog(QDialog):
    """Modeless, per-window retained choices; no folder/viewer selection is rewritten."""

    def __init__(self, ui):
        super().__init__(ui)
        self._ui = ui
        self.workflow = PhotoWorkflow()
        self._page = 0
        self.setWindowTitle(_word("photo_workflow", "Photo Workflow"))
        self.resize(900, 650)
        root = QVBoxLayout(self)
        self._count = QLabel()
        root.addWidget(self._count)
        filters = QHBoxLayout()
        self._filter = QComboBox()
        for state in ("all", "pick", "reject", "unflagged"):
            self._filter.addItem(_word(f"photo_workflow_{state}", state.title()), state)
        self._filter.currentIndexChanged.connect(self._set_filter)
        filters.addWidget(self._filter)
        self._button(filters, "photo_workflow_add", "Add viewer selection", self._add_viewer)
        self._button(filters, "photo_workflow_clear", "Clear workflow", self._clear)
        root.addLayout(filters)
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemChanged.connect(self._choose)
        root.addWidget(self._list, 1)
        actions = QHBoxLayout()
        self._button(actions, "photo_workflow_compare", "Compare highlighted", self._compare)
        for state in ("pick", "reject", "unflagged"):
            self._button(actions, f"photo_workflow_{state}", state.title(),
                         lambda _checked=False, value=state: self._mark(value))
        self._button(actions, "photo_workflow_previous", "Previous page", lambda: self._step(-1))
        self._button(actions, "photo_workflow_next", "Next page", lambda: self._step(1))
        root.addLayout(actions)
        self._comparison = _WorkflowCompare(self)
        self._comparison.setVisible(False)
        self._comparison.closed.connect(self._back)
        root.addWidget(self._comparison, 2)
        presets = QHBoxLayout()
        self._develop = QComboBox()
        self._export = QComboBox()
        presets.addWidget(self._develop)
        self._button(presets, "photo_workflow_apply", "Apply develop preset", self._apply)
        presets.addWidget(self._export)
        self._button(presets, "batch_export_title", "Batch Export", self._export_selected)
        self._button(presets, "photo_workflow_back", "Back to selection", self._back)
        root.addLayout(presets)
        self._develop.currentTextChanged.connect(self._remember_develop)
        self._export.currentIndexChanged.connect(self._remember_export)
        self.refresh_presets()
        self._refresh()

    def _button(self, layout, key, fallback, slot):
        button = QPushButton(_word(key, fallback))
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def add_paths(self, paths) -> None:
        """Add cross-folder sources without resetting prior choices or presets."""
        paths = tuple(dict.fromkeys(str(path) for path in paths))
        try:
            states = {path: image_index.get_cull_state(path) for path in paths}
        except sqlite3.Error as exc:
            logger.exception("Could not read workflow culling")
            self._notice(str(exc), error=True)
            return
        self.workflow.add(paths, states)
        self._refresh()

    def refresh_states(self) -> bool:
        """Reconcile external culling edits without changing unchanged manual choices."""
        try:
            states = {path: image_index.get_cull_state(path) for path in self.workflow.paths}
        except sqlite3.Error as exc:
            logger.exception("Could not refresh workflow culling")
            self._notice(str(exc), error=True)
            return False
        for path, state in states.items():
            if state != self.workflow.states[path]:
                self.workflow.mark((path,), state)
        self._refresh()
        return True

    def _add_viewer(self):
        viewer = self._ui.viewer
        selected = viewer.selected_tiles
        paths = [path for path in viewer.model.images if path in selected]
        paths.extend(sorted(selected - set(paths)))
        self.add_paths(paths)

    def _clear(self):
        self.workflow = PhotoWorkflow()
        self._page = 0
        self._filter.setCurrentIndex(0)
        self._comparison.set_pair(None, None)
        self._back()
        self.refresh_presets()
        self._refresh()

    def _set_filter(self):
        self.workflow.set_filter(self._filter.currentData())
        self._page = 0
        self._refresh()

    def _step(self, step):
        count = len(self.workflow.visible_paths())
        self._page = max(0, min(self._page + step, max(0, (count - 1) // PAGE_SIZE)))
        self._refresh()

    def _refresh(self):
        highlighted = {item.text() for item in self._list.selectedItems()}
        paths = self.workflow.visible_paths()
        self._page = min(self._page, max(0, (len(paths) - 1) // PAGE_SIZE))
        with QSignalBlocker(self._list):
            self._list.clear()
            for path in paths[self._page * PAGE_SIZE:(self._page + 1) * PAGE_SIZE]:
                item = QListWidgetItem(path, self._list)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if path in self.workflow.selected
                                   else Qt.CheckState.Unchecked)
                item.setSelected(path in highlighted)
                item.setToolTip(self.workflow.states[path])
        self._update_count()

    def _update_count(self):
        self._count.setText(_word("photo_workflow_count",
                                 "Checked: {selected}/{total}; visible: {visible}; page: {page}. "
                                 "Filtered choices remain selected.").format(
            selected=len(self.workflow.targets()), total=len(self.workflow.paths),
            visible=len(self.workflow.visible_paths()), page=self._page + 1,
        ))

    def _choose(self, item):
        self.workflow.choose(item.text(), item.checkState() == Qt.CheckState.Checked)
        if self.workflow.states[item.text()] == "reject":
            with QSignalBlocker(self._list):
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_count()

    def _mark(self, state):
        paths = tuple(item.text() for item in self._list.selectedItems())
        if not paths:
            return
        try:
            with image_index.write_batch():
                for path in paths:
                    image_index.set_cull_state(path, state)
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            logger.exception("Could not update workflow culling")
            self._notice(str(exc), error=True)
            return
        self.workflow.mark(paths, state)
        self._refresh()

    def _compare(self):
        self._pair_paths = tuple(self._list.item(i).text() for i in range(self._list.count())
                                 if self._list.item(i).isSelected())
        if len(self._pair_paths) < 2:
            self._notice(_word(
                "photo_workflow_need_pair", "Highlight at least two photos to compare",
            ))
            return
        self._pair_index = 0
        self._comparison.set_pair(*self._pair_paths[:2])
        self._comparison.setVisible(True)

    def _advance_comparison(self, step):
        paths = getattr(self, "_pair_paths", ())
        if paths:
            self._pair_index = self._comparison.step_pair_in_list(
                list(paths), self._pair_index, step,
            )

    def _back(self):
        self._comparison.setVisible(False)

    def refresh_presets(self) -> None:
        """Reuse named develop presets and the existing export catalogue on every return."""
        with QSignalBlocker(self._develop), QSignalBlocker(self._export):
            self._develop.clear()
            self._develop.addItem(_word("photo_workflow_preset", "Choose develop preset"), "")
            self._develop.addItems(DevelopPresetStore(user_setting_dict).names())
            index = self._develop.findText(self.workflow.develop_preset)
            self._develop.setCurrentIndex(max(0, index))
            self._export.clear()
            self._export.addItem(_word(
                "photo_workflow_export_default", "Default export settings",
            ), "")
            for preset in export_presets.builtin_presets():
                self._export.addItem(preset.label, preset.key)
            self._export.setCurrentIndex(max(0, self._export.findData(self.workflow.export_preset)))

    def _remember_develop(self):
        self.workflow.develop_preset = (self._develop.currentText()
                                        if self._develop.currentIndex() else "")

    def _remember_export(self):
        self.workflow.export_preset = self._export.currentData() or ""

    def _apply(self):
        if not self.refresh_states():
            return
        recipe = DevelopPresetStore(user_setting_dict).get(self.workflow.develop_preset)
        targets = self.workflow.targets()
        if recipe is None or not targets:
            return
        try:
            count = apply_recipe_to_paths(recipe, targets, recipe_store)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.exception("Could not apply workflow preset")
            self._notice(str(exc), error=True)
            return
        reload_current = getattr(self._ui.viewer, "reload_current_image_with_recipe", None)
        if callable(reload_current):
            reload_current()
        self._notice(_word(
            "photo_workflow_applied", "Preset applied to {n} photos",
        ).format(n=count))

    def _export_selected(self):
        if not self.refresh_states():
            return
        targets = self.workflow.targets()
        if not targets:
            return
        dialog = BatchExportDialog(self._ui.viewer, list(targets))
        index = dialog._preset_combo.findData(self.workflow.export_preset)
        if index >= 0:
            dialog._preset_combo.setCurrentIndex(index)
        dialog.exec()
        self.workflow.export_preset = dialog._preset_combo.currentData() or ""
        dialog.deleteLater()
        self.refresh_presets()

    def _notice(self, message, *, error=False):
        self._count.setText(message)
        toast = getattr(self._ui, "toast", None)
        if toast is not None:
            (toast.error if error else toast.info)(message)


def open_photo_workflow(ui, paths=()) -> PhotoWorkflowDialog:
    """Resume a window's retained workflow and optionally append new search/selection sources."""
    dialog = getattr(ui, "_photo_workflow_dialog", None)
    if dialog is None:
        dialog = ui._photo_workflow_dialog = PhotoWorkflowDialog(ui)
    if paths:
        dialog.add_paths(paths)
    elif not dialog.workflow.paths:
        dialog._add_viewer()
    dialog.refresh_presets()
    dialog.refresh_states()
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog
