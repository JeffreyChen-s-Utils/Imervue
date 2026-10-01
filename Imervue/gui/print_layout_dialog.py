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
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.gui.file_filters import image_filter
from Imervue.gui.dialog_rows import folder_picker_row, save_path_into
from Imervue.gpu_image_view.actions.select import selection_or_all
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.image.print_layout import (
    PAGE_SIZES, PT_PER_MM, PrintLayout, export_print_pdf, leaves_room,
)
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.print_layout_dialog")

_TITLE = ("print_title", "Print Layout")
# attribute, (min, max) mm, default in points, label key / fallback, tooltip key / fallback
_SPACING_ROWS = (
    ("_margin", (0.0, 50.0), PrintLayout.margin_pt,
     ("print_margin", "Margin:"),
     ("print_margin_tooltip", "Blank border on every side of the page, in millimetres")),
    ("_gutter", (0.0, 30.0), PrintLayout.gutter_pt,
     ("print_gutter", "Gutter:"),
     ("print_gutter_tooltip", "Space between neighbouring pictures, in millimetres")),
)


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
        except Exception as exc:  # a worker must always report
            logger.exception("Print export failed: %s", exc)
            self.done.emit(False, str(exc))


class PrintLayoutDialog(WorkerHostMixin, QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._worker: _Worker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get(*_TITLE))
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
        self._rows = QSpinBox()
        self._rows.setRange(1, 10)
        self._rows.setValue(2)
        self._cols = QSpinBox()
        self._cols.setRange(1, 10)
        self._cols.setValue(2)
        self._crop_marks = QCheckBox(lang.get("print_crop_marks", "Crop marks"))

        form = QFormLayout()
        form.addRow(lang.get("print_page_size", "Page size:"), self._page_combo)
        form.addRow("", self._landscape)
        form.addRow(lang.get("print_rows", "Rows:"), self._rows)
        form.addRow(lang.get("print_cols", "Columns:"), self._cols)
        self._add_spacing_rows(form, lang)
        form.addRow("", self._crop_marks)

        out_row, self._out_edit = folder_picker_row(
            lang.get("print_output", "Output PDF:"), self._pick_out,
            browse_text=lang.get("export_browse", "Browse..."))
        self._out_edit.setText(str(Path.home() / "print_sheet.pdf"))

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

    def _add_spacing_rows(self, form: QFormLayout, lang: dict) -> None:
        """Margin and gutter spins in millimetres, stored as ``self.<attribute>``."""
        for attr, (lo, hi), default_pt, label, tooltip in _SPACING_ROWS:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(1)
            spin.setSingleStep(0.5)
            spin.setSuffix(" mm")
            spin.setValue(round(default_pt / PT_PER_MM, 1))
            spin.setToolTip(lang.get(*tooltip))
            setattr(self, attr, spin)
            form.addRow(lang.get(*label), spin)

    def _populate_from_viewer(self) -> None:
        """Start with the selected pictures, or every picture in the folder."""
        for path in selection_or_all(getattr(self._ui, "viewer", None)):
            self._files.addItem(str(path))

    def _add_files(self) -> None:
        lang = language_wrapper.language_word_dict
        fns, _ = QFileDialog.getOpenFileNames(
            self, lang.get("print_add", "Add files"), "",
            image_filter(("png", "jpg", "jpeg", "tif", "tiff")),
        )
        for fn in fns:
            self._files.addItem(fn)

    def _pick_out(self) -> None:
        lang = language_wrapper.language_word_dict
        save_path_into(
            self, self._out_edit, lang.get("print_output", "Output PDF"), "PDF (*.pdf)")

    def _layout(self) -> PrintLayout:
        """The layout the form describes, for the pictures in the list."""
        return PrintLayout(
            page_size=self._page_combo.currentText(),
            landscape=self._landscape.isChecked(),
            rows=self._rows.value(), cols=self._cols.value(),
            margin_pt=self._margin.value() * PT_PER_MM,
            gutter_pt=self._gutter.value() * PT_PER_MM,
            crop_marks=self._crop_marks.isChecked(),
            image_paths=[self._files.item(i).text() for i in range(self._files.count())],
        )

    def _refusal(self, layout: PrintLayout) -> str:
        """Why *layout* can't be exported, or ``""`` when it can."""
        lang = language_wrapper.language_word_dict
        if not layout.image_paths:
            return lang.get("print_no_images", "Add at least one picture to print.")
        if not leaves_room(layout):
            return lang.get(
                "print_no_room",
                "The margins and gutter leave no room for the pictures. "
                "Make them smaller, or use fewer rows or columns.")
        return ""

    def _run(self) -> None:
        out = self._out_edit.text().strip()
        if not out:
            return
        layout = self._layout()
        refusal = self._refusal(layout)
        if refusal:
            QMessageBox.information(self, language_wrapper.language_word_dict.get(*_TITLE), refusal)
            return
        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._worker = _Worker(layout, out)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, info: str) -> None:
        """*info* is the written PDF on success, else the error to show."""
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        lang = language_wrapper.language_word_dict
        if not ok:
            QMessageBox.warning(self, lang.get(*_TITLE),
                                lang.get("print_error", "Export failed: {err}").format(err=info))
            return
        toast = getattr(self._ui, "toast", None)
        if toast is not None:
            toast.info(lang.get("print_done", "Print layout written: {path}").format(
                path=Path(info).name))
        self.accept()


def open_print_layout(ui: ImervueMainWindow) -> None:
    PrintLayoutDialog(ui).exec()
