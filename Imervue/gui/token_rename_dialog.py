"""
Token-based batch rename dialog with live preview.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
)

from Imervue.library.token_rename import apply_plan, preview, RenamePlan
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_DEFAULT_TEMPLATE = "{name}_{counter:04}{ext}"
_TOKENS_HELP = (
    "{name} {ext} {counter} {counter:04} {date} {date:yyyymmdd} "
    "{width} {height} {wxh} {size_kb} {camera} {year} {month} {day}"
)


class TokenRenameDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow, paths: list[str]):
        super().__init__(ui)
        self._ui = ui
        self._paths = paths
        self._plans: list[RenamePlan] = []
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("token_rename_title", "Token Batch Rename"))
        self.resize(640, 440)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("token_rename_count", "{n} file(s)").format(n=len(paths))
        ))

        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel(lang.get("token_rename_template", "Template:")))
        self._template_edit = QLineEdit(_DEFAULT_TEMPLATE)
        tpl_row.addWidget(self._template_edit, stretch=1)
        tpl_row.addWidget(QLabel(lang.get("token_rename_start", "Start:")))
        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 999999)
        self._start_spin.setValue(1)
        tpl_row.addWidget(self._start_spin)
        layout.addLayout(tpl_row)

        help_label = QLabel(_TOKENS_HELP)
        help_label.setStyleSheet("color: #888; font-size: 10px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels([
            lang.get("token_rename_col_original", "Original"),
            lang.get("token_rename_col_new", "New name"),
            lang.get("token_rename_col_status", "Status"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        ok = QPushButton(lang.get("token_rename_apply", "Rename"))
        ok.clicked.connect(self._apply)
        cancel = QPushButton(lang.get("common_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        self._template_edit.textChanged.connect(self._refresh)
        self._start_spin.valueChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        self._plans = preview(
            self._paths,
            self._template_edit.text(),
            start=self._start_spin.value(),
        )
        self._table.setRowCount(len(self._plans))
        from pathlib import Path
        for i, plan in enumerate(self._plans):
            self._table.setItem(i, 0, QTableWidgetItem(Path(plan.src).name))
            self._table.setItem(i, 1, QTableWidgetItem(Path(plan.dst).name))
            status = "CONFLICT" if plan.conflict else "OK"
            self._table.setItem(i, 2, QTableWidgetItem(status))

    def _apply(self) -> None:
        lang = language_wrapper.language_word_dict
        ok, failed = apply_plan(self._plans)
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                lang.get("token_rename_done", "Renamed {ok}, failed {failed}").format(
                    ok=ok, failed=failed,
                )
            )
        # 更新 viewer model
        viewer = self._ui.viewer
        mapping = {plan.src: plan.dst for plan in self._plans if not plan.conflict}
        images = viewer.model.images
        for i, p in enumerate(images):
            if p in mapping:
                images[i] = mapping[p]
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(images)
        self.accept()


def open_token_rename(ui: ImervueMainWindow) -> None:
    selected = list(ui.viewer.selected_tiles)
    paths = selected or list(ui.viewer.model.images)
    if not paths:
        return
    TokenRenameDialog(ui, paths).exec()
