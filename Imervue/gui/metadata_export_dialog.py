"""
Metadata export dialog — writes the current view's image metadata as CSV or JSON.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QPushButton, QFileDialog, QButtonGroup,
)

from Imervue.library.metadata_export import export_csv, export_json
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class MetadataExportDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow, paths: list[str]):
        super().__init__(ui)
        self._ui = ui
        self._paths = paths
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("metadata_export_title", "Export Metadata"))
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("metadata_export_count", "Images to export: {n}").format(
                n=len(paths)
            )
        ))

        self._format_group = QButtonGroup(self)
        self._csv_radio = QRadioButton("CSV")
        self._json_radio = QRadioButton("JSON")
        self._csv_radio.setChecked(True)
        self._format_group.addButton(self._csv_radio)
        self._format_group.addButton(self._json_radio)
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.get("metadata_export_format", "Format:")))
        row.addWidget(self._csv_radio)
        row.addWidget(self._json_radio)
        row.addStretch()
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        export_btn = QPushButton(lang.get("metadata_export_apply", "Export"))
        export_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton(lang.get("common_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _apply(self) -> None:
        lang = language_wrapper.language_word_dict
        is_csv = self._csv_radio.isChecked()
        filter_str = "CSV (*.csv)" if is_csv else "JSON (*.json)"
        default_name = "imervue_metadata." + ("csv" if is_csv else "json")
        dest, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("metadata_export_save_title", "Save metadata"),
            default_name,
            filter_str,
        )
        if not dest:
            return
        suffix = ".csv" if is_csv else ".json"
        if not Path(dest).suffix:
            dest += suffix
        try:
            n = export_csv(self._paths, dest) if is_csv else export_json(self._paths, dest)
        except Exception as exc:  # noqa: BLE001
            if hasattr(self._ui, "toast"):
                self._ui.toast.error(str(exc))
            return
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                lang.get("metadata_export_done", "Exported {n} rows to {path}").format(
                    n=n, path=dest,
                )
            )
        self.accept()


def open_metadata_export(ui: ImervueMainWindow) -> None:
    paths = list(ui.viewer.model.images)
    if not paths:
        return
    MetadataExportDialog(ui, paths).exec()
