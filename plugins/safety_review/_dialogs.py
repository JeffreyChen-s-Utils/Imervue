"""Qt dialogs for the safety_review plugin.

Three user-facing dialogs (scan-all, single, batch) plus the shared
``_build_mode_row`` settings widget and the ``_ensure_deps`` dependency gate.
The dialogs are thin: they collect settings, kick off a worker from
``_workers`` and render its progress / result signals.

This module owns ``ScanAllDialog``'s widgets and stays the import location
for every dialog name. The rest lives in sibling modules: shared helpers and
the worker teardown in ``_dialogs_common``, the settings rows in
``_dialogs_widgets``, the Scan All run lifecycle in ``_dialogs_scan_run``,
and the single / batch dialogs in ``_dialogs_single`` / ``_dialogs_batch``.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

from safety_review._constants import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_PADDING,
    MODE_REAL,
    _MODE_DEFAULTS,
)
from safety_review._detection import _scan_folder
from safety_review._dialogs_batch import BatchSafetyReviewDialog
from safety_review._dialogs_common import (
    _DEFAULT_BROWSE,
    _KEY_BROWSE,
    _KEY_CANCEL,
    _KEY_OUTPUT_DIR,
    _KEY_OVERWRITE,
    _WorkerHostMixin,
    _ensure_deps,
    _fmt_time,
    _format_result_message,
    _reload_grid_or_deepzoom,
    _selected_categories,
)
from safety_review._dialogs_scan_run import _ScanAllRunMixin
from safety_review._dialogs_single import SafetyReviewDialog
from safety_review._dialogs_widgets import (
    _build_category_checks,
    _build_mode_combo,
    _build_mode_row,
    _build_shape_combo,
    _build_spin_row,
    _build_style_combo,
    _SettingsDialogBase,
)

__all__ = [
    "BatchSafetyReviewDialog",
    "SafetyReviewDialog",
    "ScanAllDialog",
    "_SettingsDialogBase",
    "_WorkerHostMixin",
    "_build_category_checks",
    "_build_mode_combo",
    "_build_mode_row",
    "_build_shape_combo",
    "_build_spin_row",
    "_build_style_combo",
    "_ensure_deps",
    "_fmt_time",
    "_format_result_message",
    "_reload_grid_or_deepzoom",
    "_selected_categories",
]


class ScanAllDialog(_ScanAllRunMixin, _WorkerHostMixin, QDialog):
    """Scan folder dialog — user picks a folder, configures mode, then starts."""

    def __init__(self, main_gui,
                 initial_paths: list[str] | None = None,
                 block_size: int = DEFAULT_BLOCK_SIZE,
                 padding: int = DEFAULT_PADDING,
                 get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = initial_paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env
        self._block_size = block_size
        self._padding = padding
        self._finished = False
        # Scanned folder root — set only when "include subfolders" is on, so a
        # separate-output run mirrors the subfolder tree instead of flattening.
        self._source_root: str | None = None
        # Failed-image folder used by the most recent run (for the summary).
        self._last_failed_dir: str | None = None

        self.setWindowTitle(
            self._lang.get("safety_review_scan_all_title",
                           "Safety Review — Scan All")
        )
        self.setMinimumWidth(500)
        self._build_ui()

        if self._paths:
            folder = str(Path(self._paths[0]).parent)
            self._folder_edit.setText(folder)
            self._update_count()

    def _build_folder_row(self, layout):
        layout.addWidget(QLabel(
            self._lang.get("safety_review_scan_folder", "Source folder:")))
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText(
            self._lang.get("safety_review_scan_folder_hint",
                           "Choose a folder containing images..."))
        self._browse_folder_btn = QPushButton(
            self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._browse_folder_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(self._browse_folder_btn)
        layout.addLayout(folder_row)

        self._recursive_check = QCheckBox(
            self._lang.get("safety_review_include_subfolders",
                           "Include subfolders (scan the whole tree)"))
        self._recursive_check.toggled.connect(self._on_recursive_toggled)
        layout.addWidget(self._recursive_check)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _build_output_row(self, layout):
        self._overwrite_check = QCheckBox(
            self._lang.get(_KEY_OVERWRITE,
                           "Overwrite original files (no backup!)"))
        self._overwrite_check.setChecked(True)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        self._out_dir_label = QLabel(
            self._lang.get(_KEY_OUTPUT_DIR, "Output folder:"))
        self._out_dir_label.setVisible(False)
        layout.addWidget(self._out_dir_label)

        out_row = QHBoxLayout()
        self._out_dir_edit = QLineEdit()
        self._out_dir_edit.setVisible(False)
        self._out_browse_btn = QPushButton(
            self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._out_browse_btn.setVisible(False)
        self._out_browse_btn.clicked.connect(self._browse_out_dir)
        out_row.addWidget(self._out_dir_edit, 1)
        out_row.addWidget(self._out_browse_btn)
        layout.addLayout(out_row)

        # Only meaningful for a separate-output run: write just the images
        # that were actually censored, leaving clean ones uncopied.
        self._only_censored_check = QCheckBox(
            self._lang.get("safety_review_only_censored",
                           "Only save censored images (skip unchanged copies)"))
        self._only_censored_check.setVisible(False)
        layout.addWidget(self._only_censored_check)

    def _build_progress_block(self, layout):
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

    def _build_buttons(self, layout):
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton(self._lang.get(_KEY_CANCEL, "Cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("safety_review_start", "Start"))
        self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._build_folder_row(layout)
        self._build_output_row(layout)
        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks, self._shape_combo) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._merge_check = QCheckBox(
            self._lang.get("safety_review_merge_regions",
                           "Merge nearby regions (cover the junction)"))
        self._merge_check.setChecked(True)
        layout.addWidget(self._merge_check)
        self._build_progress_block(layout)
        self._build_buttons(layout)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("safety_review_scan_folder", "Source folder"))
        if folder:
            self._folder_edit.setText(folder)
            self._rescan_current_folder()
            if not self._out_dir_edit.text():
                self._out_dir_edit.setText(folder)

    def _on_recursive_toggled(self, _checked):
        """Re-scan the chosen folder when the subfolder option changes."""
        if self._folder_edit.text().strip():
            self._rescan_current_folder()

    def _rescan_current_folder(self):
        """Scan the folder in the edit box, honouring the subfolder option.

        ``source_root`` is remembered only for a recursive scan so a
        separate-output run mirrors the tree; a flat scan keeps the previous
        behaviour of dropping every result into one output folder.
        """
        folder = self._folder_edit.text().strip()
        if not folder:
            return
        recursive = self._recursive_check.isChecked()
        self._paths = _scan_folder(folder, recursive=recursive)
        self._source_root = folder if recursive else None
        self._update_count()

    def _browse_out_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get(_KEY_OUTPUT_DIR, "Output folder"))
        if folder:
            self._out_dir_edit.setText(folder)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get(
                "safety_review_scan_all_info",
                "Scanning {count} images — genitalia will be mosaiced, "
                "nipples will NOT be touched.",
            ).format(count=count)
        )
        self._start_btn.setEnabled(count > 0)

    def _on_overwrite_toggled(self, checked):
        self._out_dir_label.setVisible(not checked)
        self._out_dir_edit.setVisible(not checked)
        self._out_browse_btn.setVisible(not checked)
        self._only_censored_check.setVisible(not checked)

    def _on_mode_changed(self, index):
        mode = self._mode_combo.itemData(index)
        self._padding = _MODE_DEFAULTS.get(
            mode, _MODE_DEFAULTS[MODE_REAL])["padding"]

    def _controls(self):
        return (
            self._start_btn, self._browse_folder_btn, self._mode_combo,
            self._conf_spin, self._expand_spin, self._style_combo,
            self._shape_combo, self._merge_check, self._overwrite_check,
            self._recursive_check, self._only_censored_check,
        )
