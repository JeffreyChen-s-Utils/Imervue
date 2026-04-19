"""Macro manager dialog — record, compose, replay, and delete macros."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QInputDialog, QComboBox,
)

from Imervue.macros.macro_manager import (
    manager, ACTION_REGISTRY, Macro, MacroStep,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.macro_manager_dialog")


def open_macro_manager_dialog(ui: ImervueMainWindow) -> None:
    dlg = MacroManagerDialog(ui)
    dlg.exec()


# Each action id → list of (field_label_key, kwarg_key) tuples the UI asks for.
_ACTION_FIELDS: dict[str, list[tuple[str, str]]] = {
    "set_rating": [("macro_field_rating", "rating")],
    "toggle_favorite": [("macro_field_value", "value")],
    "set_color": [("macro_field_color", "color")],
    "add_tag": [("macro_field_tag", "tag")],
    "remove_tag": [("macro_field_tag", "tag")],
}


class MacroManagerDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("macro_title", "Macros"))
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)

        # Macro list
        layout.addWidget(QLabel(lang.get("macro_list_heading", "Saved Macros")))
        self._macro_list = QListWidget()
        self._macro_list.currentRowChanged.connect(self._on_macro_selected)
        layout.addWidget(self._macro_list, stretch=1)

        macro_btn_row = QHBoxLayout()
        new_btn = QPushButton(lang.get("macro_new", "New\u2026"))
        new_btn.clicked.connect(self._new_macro)
        macro_btn_row.addWidget(new_btn)

        delete_btn = QPushButton(lang.get("macro_delete", "Delete"))
        delete_btn.clicked.connect(self._delete_macro)
        macro_btn_row.addWidget(delete_btn)

        replay_btn = QPushButton(lang.get("macro_replay", "Replay on selection"))
        replay_btn.clicked.connect(self._replay_selected)
        macro_btn_row.addWidget(replay_btn)

        # Recording toggle
        self._record_btn = QPushButton(lang.get("macro_record_start", "Start Recording"))
        self._record_btn.setCheckable(True)
        self._record_btn.toggled.connect(self._toggle_recording)
        macro_btn_row.addWidget(self._record_btn)

        layout.addLayout(macro_btn_row)

        # Step editor
        layout.addWidget(QLabel(lang.get("macro_steps_heading", "Steps")))
        self._steps_list = QListWidget()
        layout.addWidget(self._steps_list, stretch=1)

        step_row = QHBoxLayout()
        self._action_combo = QComboBox()
        for action_id in ACTION_REGISTRY:
            self._action_combo.addItem(action_id)
        step_row.addWidget(self._action_combo)

        self._kwarg_edit = QLineEdit()
        self._kwarg_edit.setPlaceholderText(lang.get(
            "macro_kwarg_placeholder", "value (e.g. 5, red, my-tag)"))
        step_row.addWidget(self._kwarg_edit, stretch=1)

        add_step_btn = QPushButton(lang.get("macro_add_step", "Add Step"))
        add_step_btn.clicked.connect(self._add_step)
        step_row.addWidget(add_step_btn)

        remove_step_btn = QPushButton(lang.get("macro_remove_step", "Remove Step"))
        remove_step_btn.clicked.connect(self._remove_step)
        step_row.addWidget(remove_step_btn)

        layout.addLayout(step_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton(lang.get("macro_close", "Close"))
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        # Initial state
        self._current_macro: Macro | None = None
        self._refresh_macro_list()
        self._update_record_button()

    # ------------------------------------------------------------------
    # Macro list
    def _refresh_macro_list(self) -> None:
        self._macro_list.clear()
        for macro in manager.list_macros():
            item = QListWidgetItem(f"{macro.name}  ({len(macro.steps)} steps)")
            item.setData(256, macro.name)
            self._macro_list.addItem(item)

    def _on_macro_selected(self, row: int) -> None:
        self._steps_list.clear()
        if row < 0:
            self._current_macro = None
            return
        macros = manager.list_macros()
        if row >= len(macros):
            self._current_macro = None
            return
        self._current_macro = macros[row]
        for step in self._current_macro.steps:
            self._steps_list.addItem(QListWidgetItem(
                f"{step.action}  {step.kwargs}"))

    def _new_macro(self) -> None:
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("macro_new_title", "New Macro"),
            lang.get("macro_new_prompt", "Name:"),
        )
        if not ok or not name.strip():
            return
        macro = Macro(name=name.strip(), steps=[])
        # Persist empty macro so user can fill it with Add Step.
        manager._persist(macro)  # noqa: SLF001 - dialog owns this API
        user_setting_dict["macro_last_name"] = macro.name
        schedule_save()
        self._refresh_macro_list()
        self._select_macro(macro.name)

    def _delete_macro(self) -> None:
        if self._current_macro is None:
            return
        name = self._current_macro.name
        lang = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self,
            lang.get("macro_delete_title", "Delete Macro"),
            lang.get("macro_delete_confirm", "Delete macro '{name}'?").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        manager.delete_macro(name)
        self._current_macro = None
        self._refresh_macro_list()
        self._steps_list.clear()

    def _replay_selected(self) -> None:
        if self._current_macro is None:
            return
        viewer = getattr(self.ui, "viewer", None)
        paths: list[str] = []
        if viewer is not None:
            selected = getattr(viewer, "selected_tiles", set())
            paths = [p for p in selected if isinstance(p, str)]
            if not paths:
                images = getattr(viewer.model, "images", [])
                idx = getattr(viewer, "current_index", -1)
                if 0 <= idx < len(images):
                    paths = [images[idx]]
        if not paths:
            return
        count = manager.replay(self.ui, self._current_macro, paths)
        if hasattr(self.ui, "toast"):
            lang = language_wrapper.language_word_dict
            self.ui.toast.info(
                lang.get("macro_replayed",
                         "Replayed {name}: {count} step(s) on {files} file(s)").format(
                    name=self._current_macro.name, count=count, files=len(paths)))

    # ------------------------------------------------------------------
    # Steps
    def _parse_kwargs(self, action_id: str, raw: str) -> dict:
        """Translate the UI's single free-form value into the action's kwargs."""
        fields = _ACTION_FIELDS.get(action_id, [])
        if not fields:
            return {}
        _, kwarg_key = fields[0]
        value = raw.strip()
        if action_id == "set_rating":
            try:
                return {kwarg_key: max(0, min(5, int(value)))}
            except ValueError:
                return {kwarg_key: 0}
        if action_id == "toggle_favorite":
            lowered = value.lower()
            if lowered in ("true", "yes", "1", "on"):
                return {kwarg_key: True}
            if lowered in ("false", "no", "0", "off"):
                return {kwarg_key: False}
            return {kwarg_key: None}
        return {kwarg_key: value or None}

    def _add_step(self) -> None:
        if self._current_macro is None:
            return
        action_id = self._action_combo.currentText()
        kwargs = self._parse_kwargs(action_id, self._kwarg_edit.text())
        step = MacroStep(action=action_id, kwargs=kwargs)
        self._current_macro.steps.append(step)
        manager._persist(self._current_macro)  # noqa: SLF001
        self._kwarg_edit.clear()
        self._select_macro(self._current_macro.name)

    def _remove_step(self) -> None:
        if self._current_macro is None:
            return
        row = self._steps_list.currentRow()
        if row < 0 or row >= len(self._current_macro.steps):
            return
        del self._current_macro.steps[row]
        manager._persist(self._current_macro)  # noqa: SLF001
        self._select_macro(self._current_macro.name)

    def _select_macro(self, name: str) -> None:
        self._refresh_macro_list()
        for i in range(self._macro_list.count()):
            item = self._macro_list.item(i)
            if item.data(256) == name:
                self._macro_list.setCurrentRow(i)
                break

    # ------------------------------------------------------------------
    # Recording
    def _toggle_recording(self, checked: bool) -> None:
        lang = language_wrapper.language_word_dict
        if checked:
            manager.start_recording()
            self._update_record_button()
            return
        if not manager.is_recording():
            return
        name, ok = QInputDialog.getText(
            self,
            lang.get("macro_save_title", "Save Macro"),
            lang.get("macro_save_prompt", "Name for this macro:"),
        )
        if not ok or not name.strip():
            manager.cancel_recording()
            self._update_record_button()
            return
        macro = manager.stop_recording(name.strip())
        self._update_record_button()
        if macro is None:
            if hasattr(self.ui, "toast"):
                self.ui.toast.info(
                    lang.get("macro_no_steps_recorded", "No steps recorded"))
            return
        self._refresh_macro_list()
        self._select_macro(macro.name)

    def _update_record_button(self) -> None:
        lang = language_wrapper.language_word_dict
        if manager.is_recording():
            self._record_btn.setChecked(True)
            self._record_btn.setText(
                lang.get("macro_record_stop", "Stop Recording\u2026"))
        else:
            self._record_btn.setChecked(False)
            self._record_btn.setText(
                lang.get("macro_record_start", "Start Recording"))
