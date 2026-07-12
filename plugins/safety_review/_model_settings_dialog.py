"""Detection-model & class settings for the safety_review plugin.

Lets the user point the YOLO detector at their own fine-tuned ``.pt``, edit the
class list (index = class id, so new classes are appended after the defaults),
and tick which classes to censor. Everything is persisted through
:mod:`_class_config`, so a fine-tuned model with extra classes works with no
code change.

Plain ``QDialog`` — no ``QOpenGLWidget`` — so no headless-CI skip marker.
"""
from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

from safety_review._class_config import (
    get_censor_classes,
    get_classes,
    set_censor_classes,
    set_classes,
)
from safety_review._detection import CUSTOM_MODEL_SETTING

logger = logging.getLogger("Imervue.plugin.safety_review")


def _classes_from_text(text: str) -> list[str]:
    """One class name per non-blank line, order preserved (index = class id)."""
    return [line.strip() for line in text.splitlines() if line.strip()]


class ModelSettingsDialog(QDialog):
    """Custom model path + editable class list + censor-class selection."""

    def __init__(self, main_window=None):
        super().__init__(main_window)
        self._lang = language_wrapper.language_word_dict
        self._censor_checks: dict[str, QCheckBox] = {}
        self.setWindowTitle(
            self._lang.get("safety_review_model_settings",
                           "Detection Model & Classes"))
        self.setMinimumWidth(460)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get("safety_review_custom_model_label",
                           "Custom model (.pt) — leave blank to use EraX:")))
        model_row = QHBoxLayout()
        self._model_edit = QLineEdit()
        browse = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._browse_model)
        clear = QPushButton(self._lang.get("safety_review_clear", "Clear"))
        clear.clicked.connect(lambda: self._model_edit.clear())
        model_row.addWidget(self._model_edit, 1)
        model_row.addWidget(browse)
        model_row.addWidget(clear)
        layout.addLayout(model_row)

        layout.addWidget(QLabel(
            self._lang.get("safety_review_classes_label",
                           "Classes (one per line; order = class id):")))
        self._classes_edit = QPlainTextEdit()
        self._classes_edit.textChanged.connect(self._rebuild_censor_checks)
        layout.addWidget(self._classes_edit)

        layout.addWidget(QLabel(
            self._lang.get("safety_review_censor_label", "Censor which classes:")))
        self._censor_box = QWidget()
        self._censor_layout = QVBoxLayout(self._censor_box)
        self._censor_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._censor_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(self._lang.get("safety_review_save", "Save"))
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _load(self):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        self._model_edit.setText(user_setting_dict.get(CUSTOM_MODEL_SETTING) or "")
        self._classes_edit.setPlainText("\n".join(get_classes()))
        self._rebuild_censor_checks()
        censored = set(get_censor_classes())
        for name, cb in self._censor_checks.items():
            cb.setChecked(name in censored)

    def _rebuild_censor_checks(self):
        prev = {name: cb.isChecked() for name, cb in self._censor_checks.items()}
        while self._censor_layout.count():
            item = self._censor_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._censor_checks = {}
        for name in _classes_from_text(self._classes_edit.toPlainText()):
            if name in self._censor_checks:
                continue
            cb = QCheckBox(name)
            cb.setChecked(prev.get(name, False))
            self._censor_layout.addWidget(cb)
            self._censor_checks[name] = cb

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._lang.get("safety_review_custom_model_label", "Model"),
            self._model_edit.text(), "YOLO weights (*.pt)")
        if path:
            self._model_edit.setText(path)

    def _save(self):
        from Imervue.user_settings.user_setting_dict import (
            schedule_save,
            user_setting_dict,
        )
        path = self._model_edit.text().strip()
        if path:
            user_setting_dict[CUSTOM_MODEL_SETTING] = path
        else:
            user_setting_dict.pop(CUSTOM_MODEL_SETTING, None)
        schedule_save()
        set_classes(_classes_from_text(self._classes_edit.toPlainText()))
        set_censor_classes(
            [name for name, cb in self._censor_checks.items() if cb.isChecked()])
        self.accept()
