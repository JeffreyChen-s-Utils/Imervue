"""
重複圖片偵測
Duplicate Image Detection — scan a folder for identical or visually similar
images using file hash (exact) and perceptual hash (pHash) comparison.

The scan worker lives in ``duplicate_detection_scan``, its clustering helpers in
``duplicate_detection_clusters`` and the select / delete flows in
``duplicate_detection_actions``; their names are re-exported here.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from Imervue.gui.dialog_rows import folder_picker_row
from Imervue.gui.duplicate_detection_actions import _COUNT_PLACEHOLDER, DuplicateActionsMixin
from Imervue.gui.duplicate_detection_clusters import (
    _build_clusters,
    _find_root,
    _flatten_hash_map,
    _union,
)
from Imervue.gui.duplicate_detection_scan import (
    _IMAGE_EXTS,
    _METHOD_EXACT,
    _dhash,
    _hamming_distance,
    _ScanWorker,
)
from Imervue.image.orientation import exif_orientation
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import as_shown_8bit
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.worker_host import WorkerHostMixin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# The scan worker and clustering names stay importable from here (callers, tests).
__all__ = [
    "_IMAGE_EXTS",
    "_METHOD_EXACT",
    "DuplicateDetectionDialog",
    "_ScanWorker",
    "_build_clusters",
    "_dhash",
    "_find_root",
    "_flatten_hash_map",
    "_hamming_distance",
    "_make_thumbnail",
    "_union",
    "open_duplicate_detection",
]

# ---------------------------------------------------------------------------
# Thumbnail helper
# ---------------------------------------------------------------------------

def _make_thumbnail(path: str, size: int = 64) -> QPixmap:
    """Create a small QPixmap thumbnail for display in the tree."""
    import numpy as np
    try:
        with Image.open(path) as src:
            code = exif_orientation(src)
            src.thumbnail((size, size), Image.Resampling.LANCZOS)
            img = as_shown_8bit(src, code)
    except IMAGE_READ_ERRORS:
        return QPixmap()
    arr = np.array(img)
    h, w = arr.shape[:2]
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class DuplicateDetectionDialog(DuplicateActionsMixin, WorkerHostMixin, QDialog):
    """Scan a folder for duplicate images."""

    # The scan worker (abortable) and the trash-delete worker; the mixin joins
    # both on reject/close. FileDeleteWorker has no abort(), so it is simply
    # waited out — the in-flight trash batch is never interrupted mid-delete.
    _worker_attrs = ("_worker", "_delete_worker")

    def __init__(self, main_gui: GPUImageView, folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._lang = language_wrapper.language_word_dict
        self._worker: _ScanWorker | None = None
        self._delete_worker = None
        self._pending_delete_items: dict = {}
        self._groups: list[list[tuple[str, int]]] = []

        self.setWindowTitle(
            self._lang.get("duplicate_title", "Find Duplicate Images"))
        self.setMinimumSize(700, 500)

        self._build_ui()

        if folder and os.path.isdir(folder):
            self._folder_edit.setText(folder)

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        # Source folder
        folder_row, self._folder_edit = folder_picker_row(
            lang.get("duplicate_source", "Source folder:"), self._browse_folder)
        layout.addLayout(folder_row)
        layout.addLayout(self._build_options_row(lang))

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addWidget(self._build_results_tree(lang), 1)
        layout.addLayout(self._build_button_row(lang))

    def _build_options_row(self, lang: dict) -> QHBoxLayout:
        """Method combo, sensitivity spin (perceptual only) and the subfolder box."""
        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel(lang.get("duplicate_method", "Method:")))
        self._method_combo = QComboBox()
        self._method_combo.addItem(
            lang.get("duplicate_exact", "Exact Match (File Hash)"), _METHOD_EXACT)
        self._method_combo.addItem(
            lang.get("duplicate_perceptual", "Perceptual (Similarity)"), "perceptual")
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        opts_row.addWidget(self._method_combo)

        opts_row.addWidget(QLabel(
            lang.get("duplicate_threshold", "Sensitivity:")))
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(0, 20)
        self._threshold_spin.setValue(5)
        self._threshold_spin.setToolTip(
            lang.get("duplicate_threshold_tip",
                      "Hamming distance threshold (0=exact, higher=more tolerant)"))
        self._threshold_spin.setEnabled(False)
        opts_row.addWidget(self._threshold_spin)

        self._recursive_check = QCheckBox(
            lang.get("duplicate_recursive", "Include subfolders"))
        opts_row.addWidget(self._recursive_check)
        return opts_row

    def _build_results_tree(self, lang: dict) -> QTreeWidget:
        """Thumbnail / filename / path / size columns, multi-select."""
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            "",  # thumbnail
            lang.get("duplicate_col_filename", "Filename"),
            lang.get("duplicate_col_path", "Path"),
            lang.get("duplicate_col_size", "Size"),
        ])
        self._tree.setColumnWidth(0, 68)
        self._tree.setColumnWidth(1, 200)
        header = self._tree.header()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        return self._tree

    def _build_button_row(self, lang: dict) -> QHBoxLayout:
        """Scan, Delete Selected and Select Redundant (both disabled until a scan), then Close."""
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton(lang.get("duplicate_scan", "Scan"))
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._delete_btn = QPushButton(
            lang.get("duplicate_delete_selected", "Delete Selected"))
        self._delete_btn.clicked.connect(self._delete_selected)
        self._delete_btn.setEnabled(False)
        btn_row.addWidget(self._delete_btn)

        self._select_redundant_btn = QPushButton(
            lang.get("duplicate_select_redundant", "Select Redundant (keep best)"))
        self._select_redundant_btn.clicked.connect(self._select_redundant)
        self._select_redundant_btn.setEnabled(False)
        btn_row.addWidget(self._select_redundant_btn)

        btn_row.addStretch()

        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        return btn_row

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self._lang.get("main_window_select_folder", "Select Folder"),
        )
        if folder:
            self._folder_edit.setText(folder)

    def _on_method_changed(self, _index: int):
        method = self._method_combo.currentData()
        self._threshold_spin.setEnabled(method == "perceptual")

    def _start_scan(self):
        folder = self._folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            return
        self._tree.clear()
        self._groups.clear()
        self._delete_btn.setEnabled(False)
        self._select_redundant_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()

        method = self._method_combo.currentData() or _METHOD_EXACT
        threshold = self._threshold_spin.value()
        recursive = self._recursive_check.isChecked()

        self._worker = _ScanWorker(folder, method, threshold, recursive, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            self._lang.get("duplicate_scanning", "Scanning: {name}").replace(
                "{name}", filename
            ))

    def _on_result(self, groups: list):
        self._groups = groups
        self._tree.clear()
        if not groups:
            self._status_label.setText(
                self._lang.get("duplicate_no_duplicates", "No duplicates found."))
            return
        self._status_label.setText(
            self._lang.get("duplicate_found", "{count} group(s) of duplicates found").replace(
                _COUNT_PLACEHOLDER, str(len(groups))
            ))
        for gi, group in enumerate(groups):
            group_item = QTreeWidgetItem(self._tree)
            group_item.setText(1, f"Group {gi + 1} ({len(group)} images)")
            group_item.setFlags(
                group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for path, size in group:
                child = QTreeWidgetItem(group_item)
                thumb = _make_thumbnail(path)
                if not thumb.isNull():
                    child.setIcon(0, thumb)
                child.setText(1, os.path.basename(path))
                child.setText(2, path)
                child.setText(3, self._format_size(size))
                child.setData(0, Qt.ItemDataRole.UserRole, path)
            group_item.setExpanded(True)
        self._delete_btn.setEnabled(True)
        self._select_redundant_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")

    def _on_finished(self):
        self._progress.hide()
        self._scan_btn.setEnabled(True)
        self._worker = None

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"


def open_duplicate_detection(main_gui: GPUImageView) -> None:
    """Open the duplicate detection dialog."""
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = DuplicateDetectionDialog(main_gui, folder)
    dlg.exec()
