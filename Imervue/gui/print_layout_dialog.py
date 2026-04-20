"""Print layout dialog — compose images onto a multi-page PDF."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.image.print_layout import PAGE_SIZES, PrintLayout, export_print_pdf
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.print_layout_dialog")


class _Worker(QThread):
    done = Signal(bool, str)

    def __init__(self, layout: PrintLayout, out: str):
        super().__init__()
        self._layout = layout
        self._out = out

    def run(self):
        try:
            export_print_pdf(self._layout, self._out)
            self.done.emit(True, self._out)
        except (ImportError, OSError, ValueError) as exc:
            logger.error("Print export failed: %s", exc, exc_info=True)
            self.done.emit(False, str(exc))


class PrintLayoutDialog(QDialog):
    def __init__(self, ui: "ImervueMainWindow"):
        super().__init__(ui)
        self._ui = ui
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("print_title", "Print Layout"))
        self.setMinimumWidth(520)

        self._files = QListWidget()
        self._files.setMinimumHeight(160)
        self._populate_from_viewer()

        add_btn = QPushButton(lang.get("print_add", "Add files..."))
        add_btn.clicked.connect(self._add_files)
        clear_btn = QPushButton(lang.get("print_clear", "Clear"))
        clear_btn.clicked.connect(self._files.clear)
        file_row = QHBoxLayout()
        file_row.addWidget(add_btn)
        file_row.addWidget(clear_btn)

        self._page_combo = QComboBox()
        self._page_combo.addItems(list(PAGE_SIZES.keys()))
        self._landscape = QCheckBox(lang.get("print_landscape", "Landscape"))
        self._rows = QSpinBox(); self._rows.setRange(1, 10); self._rows.setValue(2)
        self._cols = QSpinBox(); self._cols.setRange(1, 10); self._cols.setValue(2)
        self._crop_marks = QCheckBox(lang.get("print_crop_marks", "Crop marks"))

        form = QFormLayout()
        form.addRow(lang.get("print_page_size", "Page size:"), self._page_combo)
        form.addRow("", self._landscape)
        form.addRow(lang.get("print_rows", "Rows:"), self._rows)
        form.addRow(lang.get("print_cols", "Columns:"), self._cols)
        form.addRow("", self._crop_marks)

        self._out_edit = QLineEdit(str(Path.home() / "print_sheet.pdf"))
        browse = QPushButton(lang.get("export_browse", "Browse..."))
        browse.clicked.connect(self._pick_out)
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("print_output", "Output PDF:")))
        out_row.addWidget(self._out_edit, 1)
        out_row.addWidget(browse)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._run_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._run_btn.setText(lang.get("print_export", "Export PDF"))
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._files)
        layout.addLayout(file_row)
        layout.addLayout(form)
        layout.addLayout(out_row)
        layout.addWidget(self._progress)
        layout.addWidget(buttons)

    def _populate_from_viewer(self) -> None:
        viewer = getattr(self._ui, "viewer", None)
        model = getattr(viewer, "model", None) if viewer else None
        images = getattr(model, "images", None) if model else None
        if not images:
            return
        for img in images[:64]:
            path = getattr(img, "path", None) or str(img)
            self._files.addItem(str(path))

    def _add_files(self) -> None:
        lang = language_wrapper.language_word_dict
        fns, _ = QFileDialog.getOpenFileNames(
            self, lang.get("print_add", "Add files"), "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff)",
        )
        for fn in fns:
            self._files.addItem(fn)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        fn, _ = QFileDialog.getSaveFileName(
            self, lang.get("print_output", "Output PDF"),
            self._out_edit.text(), "PDF (*.pdf)",
        )
        if fn:
            self._out_edit.setText(fn)

    def _run(self) -> None:
        paths = [self._files.item(i).text() for i in range(self._files.count())]
        out = self._out_edit.text().strip()
        if not out:
            return
        layout = PrintLayout(
            page_size=self._page_combo.currentText(),
            landscape=self._landscape.isChecked(),
            rows=self._rows.value(), cols=self._cols.value(),
            crop_marks=self._crop_marks.isChecked(),
            image_paths=paths,
        )
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(layout, out)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        _ = info
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        if ok:
            self.accept()


def open_print_layout(ui: "ImervueMainWindow") -> None:
    PrintLayoutDialog(ui).exec()
