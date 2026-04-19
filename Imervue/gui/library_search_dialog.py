"""
Library search dialog — manage library roots, trigger background scan,
and query the indexed images by name / extension / dimensions / size.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QFileDialog, QSpinBox, QCheckBox, QProgressBar, QSplitter,
    QWidget,
)

from Imervue.library import image_index
from Imervue.library.scanner import LibraryScanThread
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


class LibrarySearchDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        self._thread: LibraryScanThread | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("library_search_title", "Library Search"))
        self.resize(900, 600)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        splitter.addWidget(self._build_roots_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(1, 1)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888;")
        layout.addWidget(self._status_label)

        self._refresh_roots()
        self._refresh_count()

    # ---------- Panels ----------

    def _build_roots_panel(self) -> QWidget:
        lang = language_wrapper.language_word_dict
        w = QWidget()
        col = QVBoxLayout(w)
        col.addWidget(QLabel(lang.get("library_roots", "Library Roots")))
        self._roots_list = QListWidget()
        col.addWidget(self._roots_list, stretch=1)

        row = QHBoxLayout()
        add_btn = QPushButton(lang.get("library_add_root", "Add"))
        add_btn.clicked.connect(self._add_root)
        rm_btn = QPushButton(lang.get("library_remove_root", "Remove"))
        rm_btn.clicked.connect(self._remove_root)
        row.addWidget(add_btn)
        row.addWidget(rm_btn)
        col.addLayout(row)

        self._phash_check = QCheckBox(lang.get("library_compute_phash", "Compute perceptual hash"))
        self._phash_check.setChecked(True)
        col.addWidget(self._phash_check)

        scan_btn = QPushButton(lang.get("library_scan", "Scan now"))
        scan_btn.clicked.connect(self._start_scan)
        col.addWidget(scan_btn)
        return w

    def _build_results_panel(self) -> QWidget:
        lang = language_wrapper.language_word_dict
        w = QWidget()
        col = QVBoxLayout(w)
        col.addWidget(QLabel(lang.get("library_search", "Search")))

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(
            lang.get("library_search_name", "Filename contains…")
        )
        col.addWidget(self._name_edit)

        form_row = QHBoxLayout()
        self._min_w = QSpinBox(); self._min_w.setRange(0, 20000); self._min_w.setSuffix(" w")
        self._min_h = QSpinBox(); self._min_h.setRange(0, 20000); self._min_h.setSuffix(" h")
        self._min_size = QSpinBox(); self._min_size.setRange(0, 1_000_000); self._min_size.setSuffix(" KB min")
        self._max_size = QSpinBox(); self._max_size.setRange(0, 1_000_000); self._max_size.setSuffix(" KB max")
        for spin in (self._min_w, self._min_h, self._min_size, self._max_size):
            form_row.addWidget(spin)
        col.addLayout(form_row)

        search_btn = QPushButton(lang.get("library_search_run", "Search"))
        search_btn.clicked.connect(self._run_search)
        col.addWidget(search_btn)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._open_selected)
        col.addWidget(self._results_list, stretch=1)
        return w

    # ---------- Actions ----------

    def _add_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add library root")
        if folder:
            image_index.add_library_root(folder)
            self._refresh_roots()

    def _remove_root(self) -> None:
        item = self._roots_list.currentItem()
        if item is None:
            return
        image_index.remove_library_root(item.text())
        self._refresh_roots()

    def _refresh_roots(self) -> None:
        self._roots_list.clear()
        for r in image_index.list_library_roots():
            self._roots_list.addItem(r)

    def _refresh_count(self) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "library_total", "Indexed images: {n}"
            ).format(n=image_index.count_images())
        )

    def _start_scan(self) -> None:
        roots = image_index.list_library_roots()
        if not roots:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._thread = LibraryScanThread(roots, with_phash=self._phash_check.isChecked())
        self._thread.progress.connect(self._on_progress)
        self._thread.done.connect(self._on_done)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, current: int, total: int, path: str) -> None:
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}  {Path(path).name}")

    def _on_done(self, total: int) -> None:
        self._progress.setVisible(False)
        self._refresh_count()
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                language_wrapper.language_word_dict.get(
                    "library_scan_done", "Indexed {n} images"
                ).format(n=total)
            )

    def _on_error(self, message: str) -> None:
        self._progress.setVisible(False)
        if hasattr(self._ui, "toast"):
            self._ui.toast.error(message)

    def _run_search(self) -> None:
        paths = image_index.search_images(
            name_contains=self._name_edit.text().strip() or None,
            min_width=self._min_w.value() or None,
            min_height=self._min_h.value() or None,
            min_size=(self._min_size.value() * 1024) or None,
            max_size=(self._max_size.value() * 1024) or None,
            limit=2000,
        )
        self._results_list.clear()
        for p in paths:
            self._results_list.addItem(p)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "library_results", "{n} result(s)"
            ).format(n=len(paths))
        )

    def _open_selected(self) -> None:
        item = self._results_list.currentItem()
        if item is None:
            return
        path = item.text()
        from Imervue.gpu_image_view.images.image_loader import open_path
        open_path(main_gui=self._ui.viewer, path=path)
        self.accept()


def open_library_search(ui: ImervueMainWindow) -> None:
    LibrarySearchDialog(ui).exec()
