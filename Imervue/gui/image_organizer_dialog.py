"""
圖片整理工具
Image Organizer — sort images into subfolders by date, resolution,
file type, file size, or fixed count.

The planning lives in :mod:`Imervue.gui.image_organizer_plan`, the worker in
:mod:`Imervue.gui.image_organizer_worker` and the layout in
:mod:`Imervue.gui.image_organizer_ui`; their names are re-exported here.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QTreeWidgetItem

from Imervue.gui.image_organizer_plan import (
    RULE_COUNT,
    RULE_DATE,
    RULE_RESOLUTION,
    RULE_SIZE,
    RULE_TYPE,
    _get_image_date,
    _get_resolution_bucket,
    _get_size_bucket,
    _get_type_bucket,
    _scan_folder,
    plan_organization,
)
from Imervue.gui.image_organizer_ui import OrganizerLayoutMixin
from Imervue.gui.image_organizer_worker import _OrganizerWorker
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.system.file_transfer import follow_saved_data

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

__all__ = [
    "RULE_COUNT",
    "RULE_DATE",
    "RULE_RESOLUTION",
    "RULE_SIZE",
    "RULE_TYPE",
    "ImageOrganizerDialog",
    "_OrganizerWorker",
    "_get_image_date",
    "_get_resolution_bucket",
    "_get_size_bucket",
    "_get_type_bucket",
    "_scan_folder",
    "open_image_organizer",
    "plan_organization",
]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ImageOrganizerDialog(WorkerHostMixin, OrganizerLayoutMixin, QDialog):
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

    # ---- Helpers ----

    def _set_widgets_visible(self, widgets: list, visible: bool):
        for w in widgets:
            w.setVisible(visible)

    def _on_rule_changed(self, _index: int):
        rule = self._rule_combo.currentData()
        self._set_widgets_visible(self._date_row_widgets, rule == RULE_DATE)
        self._set_widgets_visible(self._size_row_widgets, rule == RULE_SIZE)
        self._set_widgets_visible(self._count_row_widgets, rule == RULE_COUNT)
        # Changing the rule makes any previewed plan stale — force a re-Preview.
        self._invalidate_plan()

    def _invalidate_plan(self, *_args) -> None:
        """A previewed plan is stale once any plan input changes.

        ``_do_start`` executes ``_last_plan`` captured at Preview time. Without
        this, changing the rule / options / source folder after previewing and
        then clicking Start would move or copy files by a plan the UI no longer
        shows (e.g. files organised into date folders while the dropdown reads
        "File Type"). Clearing the plan and disabling Start forces the user to
        re-Preview, so the executed plan always matches the visible settings.
        """
        self._last_plan = {}
        self._start_btn.setEnabled(False)

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
        return {
            "rule": rule,
            "year_only": self._date_combo.currentData() if rule == RULE_DATE else False,
            "large_mb": self._size_large_spin.value(),
            "small_mb": self._size_small_spin.value(),
            "count_per_folder": self._count_spin.value(),
        }

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
        self._worker.files_moved.connect(self._on_files_moved)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._status_label.setText(
            self._lang.get("organizer_processing", "Processing: {name}")
            .replace("{name}", filename))

    def _on_files_moved(self, moved: dict) -> None:
        # A bound method, so the queued signal runs this on the dialog's (GUI) thread.
        follow_saved_data(moved)

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def open_image_organizer(main_gui: GPUImageView) -> None:
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = ImageOrganizerDialog(main_gui, folder)
    dlg.exec()
