"""Contact sheet PDF export dialog."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QPushButton, QFileDialog, QCheckBox, QLineEdit, QFormLayout, QMessageBox,
)

from Imervue.export.contact_sheet import (
    ContactSheetOptions, PAGE_SIZES, generate_contact_sheet,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.contact_sheet_dialog")

_DEFAULT_TITLE = "Contact Sheet PDF"


def _title() -> str:
    return language_wrapper.language_word_dict.get("contact_sheet_title", _DEFAULT_TITLE)


def open_contact_sheet_dialog(ui: ImervueMainWindow) -> None:
    dlg = ContactSheetDialog(ui)
    dlg.exec()


class _RenderWorkerSignals(QObject):
    done = Signal(str, str)  # (output_path, error or empty string)


class _RenderWorker(QRunnable):
    def __init__(self, images: list[str], out: str, opts: ContactSheetOptions):
        super().__init__()
        self.images = images
        self.out = out
        self.opts = opts
        self.signals = _RenderWorkerSignals()

    def run(self) -> None:
        try:
            generate_contact_sheet(self.images, self.out, self.opts)
        except (OSError, ValueError) as exc:
            self.signals.done.emit(self.out, str(exc))
            return
        self.signals.done.emit(self.out, "")


class ContactSheetDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self.ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(_title())
        self.setMinimumSize(420, 300)

        layout = QVBoxLayout(self)

        images = self._resolve_images()
        layout.addWidget(QLabel(lang.get(
            "contact_sheet_source",
            "{count} image(s) will be included.").format(count=len(images))))

        form = QFormLayout()

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 20)
        self._rows_spin.setValue(5)
        form.addRow(lang.get("contact_sheet_rows", "Rows"), self._rows_spin)

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 20)
        self._cols_spin.setValue(4)
        form.addRow(lang.get("contact_sheet_cols", "Columns"), self._cols_spin)

        self._page_combo = QComboBox()
        for key in PAGE_SIZES:
            self._page_combo.addItem(key)
        form.addRow(lang.get("contact_sheet_page_size", "Page Size"), self._page_combo)

        self._margin_spin = QSpinBox()
        self._margin_spin.setRange(0, 50)
        self._margin_spin.setValue(10)
        self._margin_spin.setSuffix(" mm")
        form.addRow(lang.get("contact_sheet_margin", "Margin"), self._margin_spin)

        self._caption_check = QCheckBox(lang.get(
            "contact_sheet_caption", "Show filename under each image"))
        self._caption_check.setChecked(True)
        form.addRow("", self._caption_check)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText(lang.get(
            "contact_sheet_title_placeholder", "Optional title"))
        form.addRow(lang.get("contact_sheet_title_label", "Title"), self._title_edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._export_btn = QPushButton(lang.get("contact_sheet_export", "Export PDF\u2026"))
        self._export_btn.clicked.connect(lambda: self._export(images))
        btn_row.addWidget(self._export_btn)

        close_btn = QPushButton(lang.get("contact_sheet_close", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _resolve_images(self) -> list[str]:
        viewer = getattr(self.ui, "viewer", None)
        if viewer is None:
            return []
        selected = getattr(viewer, "selected_tiles", set())
        paths = [p for p in selected if isinstance(p, str)]
        if paths:
            return paths
        return list(getattr(viewer.model, "images", []))

    def _export(self, images: list[str]) -> None:
        lang = language_wrapper.language_word_dict
        if not images:
            QMessageBox.information(
                self,
                _title(),
                lang.get("contact_sheet_no_images", "No images to export."),
            )
            return
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("contact_sheet_save_title", "Save Contact Sheet"),
            "contact_sheet.pdf",
            "PDF (*.pdf)",
        )
        if not out_path:
            return
        if not out_path.lower().endswith(".pdf"):
            out_path += ".pdf"
        opts = ContactSheetOptions(
            rows=self._rows_spin.value(),
            cols=self._cols_spin.value(),
            page_size=self._page_combo.currentText(),
            margin_mm=float(self._margin_spin.value()),
            caption=self._caption_check.isChecked(),
            title=self._title_edit.text().strip(),
        )
        self._export_btn.setEnabled(False)
        worker = _RenderWorker(list(images), out_path, opts)
        worker.signals.done.connect(self._on_render_done)
        QThreadPool.globalInstance().start(worker)

    def _on_render_done(self, out_path: str, error: str) -> None:
        self._export_btn.setEnabled(True)
        lang = language_wrapper.language_word_dict
        if error:
            QMessageBox.warning(
                self,
                _title(),
                lang.get("contact_sheet_error", "Export failed: {err}").format(err=error),
            )
            return
        if hasattr(self.ui, "toast"):
            self.ui.toast.info(lang.get(
                "contact_sheet_done",
                "Contact sheet written: {path}").format(path=Path(out_path).name))
        self.close()
