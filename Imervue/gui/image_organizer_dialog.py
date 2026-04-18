"""
圖片整理工具
Image Organizer — sort images into subfolders by date, resolution,
file type, file size, or fixed count.
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
import contextlib

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.image_organizer")

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng",
})

RULE_DATE = "date"
RULE_RESOLUTION = "resolution"
RULE_TYPE = "type"
RULE_SIZE = "size"
RULE_COUNT = "count"


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

def _scan_folder(folder: str) -> list[str]:
    """Return image paths in *folder* (non-recursive), sorted by name."""
    result: list[str] = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and Path(entry.name).suffix.lower() in _IMAGE_EXTS:
                result.append(entry.path)
    except OSError:
        pass
    result.sort(key=lambda p: os.path.basename(p).lower())
    return result


# ---------------------------------------------------------------------------
# Planning — pure function, no side effects
# ---------------------------------------------------------------------------

def _get_image_date(path: str, year_only: bool) -> str:
    """Return a date-based subfolder name for *path*."""
    fmt = "%Y" if year_only else "%Y-%m"
    # Try EXIF DateTimeOriginal (tag 36867)
    with contextlib.suppress(Exception), Image.open(path) as img:
        exif = img.getexif()
        if exif:
            raw = exif.get(36867) or exif.get(306)  # DateTimeOriginal or DateTime
            if raw:
                dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                return dt.strftime(fmt)
    # Fallback: file modification time
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime(fmt)
    except OSError:
        return "unknown"


def _get_resolution_bucket(path: str) -> str:
    """Classify image by its longer edge."""
    try:
        with Image.open(path) as img:
            w, h = img.size
        longest = max(w, h)
        if longest >= 3840:
            return "4K+"
        if longest >= 1920:
            return "1080p+"
        if longest >= 1280:
            return "720p+"
        return "small"
    except Exception:
        return "unknown"


def _get_type_bucket(path: str) -> str:
    """Return a normalised extension group name."""
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "JPG"
    return ext.lstrip(".").upper() or "OTHER"


def _get_size_bucket(path: str, large_mb: float, small_mb: float) -> str:
    """Classify by file size."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "unknown"
    if size >= large_mb * 1024 * 1024:
        return "large"
    if size >= small_mb * 1024 * 1024:
        return "medium"
    return "small"


def plan_organization(
    paths: list[str],
    rule: str,
    *,
    year_only: bool = False,
    large_mb: float = 5.0,
    small_mb: float = 1.0,
    count_per_folder: int = 100,
) -> dict[str, list[str]]:
    """Return ``{subfolder_name: [paths]}`` without touching the filesystem."""
    plan: dict[str, list[str]] = {}
    for i, p in enumerate(paths):
        if rule == RULE_DATE:
            bucket = _get_image_date(p, year_only)
        elif rule == RULE_RESOLUTION:
            bucket = _get_resolution_bucket(p)
        elif rule == RULE_TYPE:
            bucket = _get_type_bucket(p)
        elif rule == RULE_SIZE:
            bucket = _get_size_bucket(p, large_mb, small_mb)
        elif rule == RULE_COUNT:
            bucket = f"{(i // count_per_folder) + 1:03d}"
        else:
            bucket = "other"
        plan.setdefault(bucket, []).append(p)
    return plan


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class _OrganizerWorker(QThread):
    progress = Signal(int, int, str)   # current, total, filename
    result_ready = Signal(int, int)    # success, failed

    def __init__(
        self,
        plan: dict[str, list[str]],
        output_dir: str,
        move: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._plan = plan
        self._output_dir = output_dir
        self._move = move
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        total = sum(len(v) for v in self._plan.values())
        done = 0
        success = 0
        failed = 0
        for subfolder, paths in self._plan.items():
            dest_dir = os.path.join(self._output_dir, subfolder)
            os.makedirs(dest_dir, exist_ok=True)
            for src in paths:
                if self._abort:
                    self.result_ready.emit(success, failed)
                    return
                done += 1
                name = os.path.basename(src)
                self.progress.emit(done, total, name)
                dest = os.path.join(dest_dir, name)
                # Handle name collision
                if os.path.exists(dest):
                    stem = Path(name).stem
                    ext = Path(name).suffix
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(dest_dir, f"{stem}_{counter}{ext}")
                        counter += 1
                try:
                    if self._move:
                        shutil.move(src, dest)
                    else:
                        shutil.copy2(src, dest)
                    success += 1
                except Exception:
                    logger.exception("Failed to %s %s",
                                     "move" if self._move else "copy", src)
                    failed += 1
        self.result_ready.emit(success, failed)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ImageOrganizerDialog(QDialog):
    def __init__(self, main_gui: GPUImageView, folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._lang = language_wrapper.language_word_dict
        self._worker: _OrganizerWorker | None = None

        self.setWindowTitle(self._lang.get("organizer_title", "Image Organizer"))
        self.setMinimumSize(700, 520)
        self._build_ui()

        if folder and os.path.isdir(folder):
            self._src_edit.setText(folder)

    # ---- UI ----

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        # Source folder
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel(lang.get("organizer_source", "Source folder:")))
        self._src_edit = QLineEdit()
        src_row.addWidget(self._src_edit, 1)
        src_browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        src_browse.clicked.connect(self._browse_src)
        src_row.addWidget(src_browse)
        layout.addLayout(src_row)

        # Rule selector
        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel(lang.get("organizer_rule", "Organize by:")))
        self._rule_combo = QComboBox()
        self._rule_combo.addItem(lang.get("organizer_rule_date", "Date"), RULE_DATE)
        self._rule_combo.addItem(
            lang.get("organizer_rule_resolution", "Resolution"), RULE_RESOLUTION
        )
        self._rule_combo.addItem(lang.get("organizer_rule_type", "File Type"), RULE_TYPE)
        self._rule_combo.addItem(lang.get("organizer_rule_size", "File Size"), RULE_SIZE)
        self._rule_combo.addItem(lang.get("organizer_rule_count", "Fixed Count"), RULE_COUNT)
        self._rule_combo.currentIndexChanged.connect(self._on_rule_changed)
        rule_row.addWidget(self._rule_combo, 1)
        layout.addLayout(rule_row)

        # --- Rule-specific options ---

        # Date options
        self._date_row = QHBoxLayout()
        self._date_row_widgets: list = []
        lbl = QLabel(lang.get("organizer_date_granularity", "Group by:"))
        self._date_row.addWidget(lbl)
        self._date_row_widgets.append(lbl)
        self._date_combo = QComboBox()
        self._date_combo.addItem(lang.get("organizer_date_year_month", "Year-Month"), False)
        self._date_combo.addItem(lang.get("organizer_date_year", "Year only"), True)
        self._date_row.addWidget(self._date_combo)
        self._date_row_widgets.append(self._date_combo)
        self._date_row.addStretch()
        layout.addLayout(self._date_row)

        # Size options
        self._size_row = QHBoxLayout()
        self._size_row_widgets: list = []
        lbl2 = QLabel(lang.get("organizer_size_large", "Large threshold (MB):"))
        self._size_row.addWidget(lbl2)
        self._size_row_widgets.append(lbl2)
        self._size_large_spin = QSpinBox()
        self._size_large_spin.setRange(1, 1000)
        self._size_large_spin.setValue(5)
        self._size_row.addWidget(self._size_large_spin)
        self._size_row_widgets.append(self._size_large_spin)
        lbl3 = QLabel(lang.get("organizer_size_small", "Small threshold (MB):"))
        self._size_row.addWidget(lbl3)
        self._size_row_widgets.append(lbl3)
        self._size_small_spin = QSpinBox()
        self._size_small_spin.setRange(0, 999)
        self._size_small_spin.setValue(1)
        self._size_row.addWidget(self._size_small_spin)
        self._size_row_widgets.append(self._size_small_spin)
        self._size_row.addStretch()
        layout.addLayout(self._size_row)

        # Count options
        self._count_row = QHBoxLayout()
        self._count_row_widgets: list = []
        lbl4 = QLabel(lang.get("organizer_count_per_folder", "Images per subfolder:"))
        self._count_row.addWidget(lbl4)
        self._count_row_widgets.append(lbl4)
        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 10000)
        self._count_spin.setValue(100)
        self._count_row.addWidget(self._count_spin)
        self._count_row_widgets.append(self._count_spin)
        self._count_row.addStretch()
        layout.addLayout(self._count_row)

        # Output folder
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(lang.get("organizer_output", "Output folder:")))
        self._out_edit = QLineEdit()
        out_row.addWidget(self._out_edit, 1)
        out_browse = QPushButton(lang.get("batch_convert_browse", "Browse..."))
        out_browse.clicked.connect(self._browse_out)
        out_row.addWidget(out_browse)
        layout.addLayout(out_row)

        # Copy / Move
        mode_row = QHBoxLayout()
        self._copy_radio = QRadioButton(lang.get("organizer_mode_copy", "Copy files"))
        self._move_radio = QRadioButton(lang.get("organizer_mode_move", "Move files"))
        self._copy_radio.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._copy_radio)
        grp.addButton(self._move_radio)
        mode_row.addWidget(self._copy_radio)
        mode_row.addWidget(self._move_radio)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Preview tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Subfolder / File", "Count"])
        self._tree.setColumnWidth(0, 450)
        layout.addWidget(self._tree, 1)

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton(lang.get("organizer_preview", "Preview"))
        self._preview_btn.clicked.connect(self._do_preview)
        btn_row.addWidget(self._preview_btn)

        self._start_btn = QPushButton(lang.get("organizer_start", "Start"))
        self._start_btn.clicked.connect(self._do_start)
        self._start_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)

        btn_row.addStretch()
        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # Initial visibility
        self._on_rule_changed(0)

    # ---- Helpers ----

    def _set_widgets_visible(self, widgets: list, visible: bool):
        for w in widgets:
            w.setVisible(visible)

    def _on_rule_changed(self, _index: int):
        rule = self._rule_combo.currentData()
        self._set_widgets_visible(self._date_row_widgets, rule == RULE_DATE)
        self._set_widgets_visible(self._size_row_widgets, rule == RULE_SIZE)
        self._set_widgets_visible(self._count_row_widgets, rule == RULE_COUNT)

    def _browse_src(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._src_edit.setText(folder)
            if not self._out_edit.text().strip():
                self._out_edit.setText(folder)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._out_edit.setText(folder)

    # ---- Preview ----

    def _current_plan_kwargs(self) -> dict:
        rule = self._rule_combo.currentData() or RULE_DATE
        return dict(
            rule=rule,
            year_only=self._date_combo.currentData() if rule == RULE_DATE else False,
            large_mb=self._size_large_spin.value(),
            small_mb=self._size_small_spin.value(),
            count_per_folder=self._count_spin.value(),
        )

    def _do_preview(self):
        src = self._src_edit.text().strip()
        if not src or not os.path.isdir(src):
            return
        paths = _scan_folder(src)
        if not paths:
            self._status_label.setText(
                self._lang.get("organizer_no_images", "No images found in source folder."))
            self._tree.clear()
            self._start_btn.setEnabled(False)
            return

        self._last_plan = plan_organization(paths, **self._current_plan_kwargs())
        self._tree.clear()
        total_files = 0
        for subfolder in sorted(self._last_plan.keys()):
            files = self._last_plan[subfolder]
            total_files += len(files)
            parent = QTreeWidgetItem(self._tree)
            parent.setText(0, subfolder)
            parent.setText(1, str(len(files)))
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for p in files:
                child = QTreeWidgetItem(parent)
                child.setText(0, os.path.basename(p))
            parent.setExpanded(False)

        summary = (self._lang
                   .get("organizer_preview_summary",
                        "{count} images into {folders} subfolder(s)")
                   .replace("{count}", str(total_files))
                   .replace("{folders}", str(len(self._last_plan))))
        self._status_label.setText(summary)
        self._start_btn.setEnabled(True)

    # ---- Execute ----

    def _do_start(self):
        out = self._out_edit.text().strip()
        if not out:
            return
        if not hasattr(self, "_last_plan") or not self._last_plan:
            return

        os.makedirs(out, exist_ok=True)
        self._start_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()

        self._worker = _OrganizerWorker(
            self._last_plan, out, move=self._move_radio.isChecked(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            self._lang.get("organizer_processing", "Processing: {name}")
            .replace("{name}", filename))

    def _on_result(self, success: int, failed: int):
        self._status_label.setText(
            self._lang.get("organizer_done",
                           "Done — {success} organized, {failed} failed.")
            .replace("{success}", str(success))
            .replace("{failed}", str(failed)))

    def _on_finished(self):
        self._progress.hide()
        self._start_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._worker = None

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            with contextlib.suppress(RuntimeError, TypeError):
                self._worker.disconnect()
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def open_image_organizer(main_gui: GPUImageView) -> None:
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = ImageOrganizerDialog(main_gui, folder)
    dlg.exec()
