"""
重複圖片偵測
Duplicate Image Detection — scan a folder for identical or visually similar
images using file hash (exact) and perceptual hash (pHash) comparison.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.duplicate_detection")

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng",
})


# ---------------------------------------------------------------------------
# Perceptual hash — difference hash (dHash)
# ---------------------------------------------------------------------------

def _dhash(img: Image.Image, hash_size: int = 8) -> int:
    """Compute a difference hash (dHash) for an image.

    Resizes to (hash_size+1, hash_size), converts to grayscale, then
    compares adjacent pixel brightness to build a binary fingerprint.
    Very fast and surprisingly effective for near-duplicate detection.
    """
    resized = img.convert("L").resize(
        (hash_size + 1, hash_size), Image.Resampling.LANCZOS
    )
    # Pillow 14+ renamed getdata() → get_flattened_data(); support both.
    _get = getattr(resized, "get_flattened_data", None) or resized.getdata
    pixels = list(_get())
    w = hash_size + 1
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * w + col
            if pixels[idx] < pixels[idx + 1]:
                bits |= 1 << (row * hash_size + col)
    return bits


def _hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two integers."""
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class _ScanWorker(QThread):
    """Scans a folder for duplicate images."""
    progress = Signal(int, int, str)      # current, total, filename
    result_ready = Signal(list)           # list of groups: [(path, hash, size), ...]
    error = Signal(str)

    def __init__(
        self,
        folder: str,
        method: str,           # "exact" or "perceptual"
        threshold: int,        # hamming distance threshold for perceptual
        recursive: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._folder = folder
        self._method = method
        self._threshold = threshold
        self._recursive = recursive
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            paths = self._collect_paths()
            if not paths:
                self.result_ready.emit([])
                return

            total = len(paths)
            hash_map: dict[str, list[tuple[str, int]]] = {}  # hash_key → [(path, size)]

            for i, path in enumerate(paths):
                if self._abort:
                    return
                self.progress.emit(i + 1, total, os.path.basename(path))
                try:
                    fsize = os.path.getsize(path)
                    if self._method == "exact":
                        h = self._file_hash(path)
                    else:
                        h = self._perceptual_hash(path)
                    hash_map.setdefault(h, []).append((path, fsize))
                except Exception:
                    logger.debug("Skipping %s", path, exc_info=True)
                    continue

            if self._method == "exact":
                # Group by identical hash
                groups = [g for g in hash_map.values() if len(g) > 1]
            else:
                # Group by hamming distance
                groups = self._cluster_perceptual(hash_map)

            self.result_ready.emit(groups)
        except Exception as e:
            logger.exception("Duplicate scan failed")
            self.error.emit(str(e))

    def _collect_paths(self) -> list[str]:
        result = []
        if self._recursive:
            for root, _dirs, files in os.walk(self._folder):
                if self._abort:
                    break
                for f in files:
                    if Path(f).suffix.lower() in _IMAGE_EXTS:
                        result.append(os.path.join(root, f))
        else:
            try:
                for entry in os.scandir(self._folder):
                    if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                        result.append(entry.path)
            except OSError:
                pass
        result.sort(key=lambda p: os.path.basename(p).lower())
        return result

    @staticmethod
    def _file_hash(path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _perceptual_hash(path: str) -> str:
        img = Image.open(path)
        return str(_dhash(img))

    def _cluster_perceptual(
        self,
        hash_map: dict[str, list[tuple[str, int]]],
    ) -> list[list[tuple[str, int]]]:
        """Cluster perceptual hashes by hamming distance."""
        # First: identical hashes are always duplicates
        entries: list[tuple[int, str, int]] = []  # (hash_int, path, size)
        for h_str, items in hash_map.items():
            h_int = int(h_str)
            for path, size in items:
                entries.append((h_int, path, size))

        n = len(entries)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # O(n^2) but n is typically small (folder of images)
        for i in range(n):
            if self._abort:
                return []
            for j in range(i + 1, n):
                if _hamming_distance(entries[i][0], entries[j][0]) <= self._threshold:
                    union(i, j)

        from collections import defaultdict
        clusters: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append((entries[i][1], entries[i][2]))

        return [g for g in clusters.values() if len(g) > 1]


# ---------------------------------------------------------------------------
# Thumbnail helper
# ---------------------------------------------------------------------------

def _make_thumbnail(path: str, size: int = 64) -> QPixmap:
    """Create a small QPixmap thumbnail for display in the tree."""
    try:
        img = Image.open(path)
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        import numpy as np
        arr = np.array(img)
        h, w = arr.shape[:2]
        qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimg)
    except Exception:
        return QPixmap()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class DuplicateDetectionDialog(QDialog):
    """Scan a folder for duplicate images."""

    def __init__(self, main_gui: "GPUImageView", folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._lang = language_wrapper.language_word_dict
        self._worker: _ScanWorker | None = None
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
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel(lang.get("duplicate_source", "Source folder:")))
        self._folder_edit = QLineEdit()
        folder_row.addWidget(self._folder_edit, 1)
        browse_btn = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Options row
        opts_row = QHBoxLayout()
        opts_row.addWidget(QLabel(lang.get("duplicate_method", "Method:")))
        self._method_combo = QComboBox()
        self._method_combo.addItem(
            lang.get("duplicate_exact", "Exact Match (File Hash)"), "exact")
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
        layout.addLayout(opts_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Results tree
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
        layout.addWidget(self._tree, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton(lang.get("duplicate_scan", "Scan"))
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._delete_btn = QPushButton(
            lang.get("duplicate_delete_selected", "Delete Selected"))
        self._delete_btn.clicked.connect(self._delete_selected)
        self._delete_btn.setEnabled(False)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()

        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

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
        self._scan_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()

        method = self._method_combo.currentData() or "exact"
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
                "{count}", str(len(groups))
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

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")

    def _on_finished(self):
        self._progress.hide()
        self._scan_btn.setEnabled(True)
        self._worker = None

    def _delete_selected(self):
        items = self._tree.selectedItems()
        paths = []
        for item in items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                paths.append((item, path))
        if not paths:
            return
        reply = QMessageBox.question(
            self,
            self._lang.get("duplicate_confirm_title", "Confirm Delete"),
            self._lang.get(
                "duplicate_confirm_msg",
                "Move {count} file(s) to trash?"
            ).replace("{count}", str(len(paths))),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted = 0
        for item, path in paths:
            try:
                from send2trash import send2trash
                send2trash(path)
                parent = item.parent()
                if parent:
                    parent.removeChild(item)
                deleted += 1
            except Exception:
                logger.exception("Failed to delete %s", path)
        self._status_label.setText(
            self._lang.get("duplicate_deleted", "{count} file(s) deleted").replace(
                "{count}", str(deleted)
            ))

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


def open_duplicate_detection(main_gui: "GPUImageView") -> None:
    """Open the duplicate detection dialog."""
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = DuplicateDetectionDialog(main_gui, folder)
    dlg.exec()
