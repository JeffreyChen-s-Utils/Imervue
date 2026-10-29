"""Batch safety_review dialog for the selected images."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper

from safety_review._constants import SHAPE_PRECISE
from safety_review._dialogs_common import (
    _DEFAULT_BROWSE,
    _DEFAULT_INFO,
    _DEFAULT_INSTALLING,
    _KEY_BROWSE,
    _KEY_CANCEL,
    _KEY_INFO,
    _KEY_INSTALLING,
    _KEY_OUTPUT_DIR,
    _KEY_OVERWRITE,
    _KEY_RUN,
    _ensure_deps,
    _format_result_message,
    _reload_grid_or_deepzoom,
)
from safety_review._dialogs_widgets import _build_mode_row, _SettingsDialogBase
from safety_review._workers import _BatchWorker, _SubprocessBatchWorker


class BatchSafetyReviewDialog(_SettingsDialogBase):
    """Batch dialog — selected images, choose overwrite or separate output."""

    def __init__(self, main_gui, paths: list[str], get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_batch_title", "Batch Safety Review")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_output_row(self, layout):
        self._overwrite_check = QCheckBox(
            self._lang.get(_KEY_OVERWRITE,
                           "Overwrite original files (no backup!)"))
        self._overwrite_check.setChecked(False)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

        self._dir_label = QLabel(self._lang.get(_KEY_OUTPUT_DIR, "Output folder:"))
        layout.addWidget(self._dir_label)
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        self._browse_btn = QPushButton(self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        self._browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(self._browse_btn)
        layout.addLayout(dir_row)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            self._lang.get("batch_export_count", "{count} image(s) selected")
            .format(count=len(self._paths))
        ))
        info = QLabel(self._lang.get(_KEY_INFO, _DEFAULT_INFO))
        info.setWordWrap(True)
        layout.addWidget(info)

        (self._mode_combo, self._conf_spin, self._expand_spin,
         self._style_combo, self._cat_checks, self._shape_combo) = _build_mode_row(
            layout, self._lang)
        self._mode_combo.currentIndexChanged.connect(
            self._on_mode_changed_padding)

        self._build_block_padding_rows(layout)
        self._build_output_row(layout)

        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        self._time_label = QLabel("")
        layout.addWidget(self._time_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get(_KEY_CANCEL, "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(self._lang.get(_KEY_RUN, "Apply Mosaic"))
        self._run_btn.clicked.connect(self._do_run)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _on_overwrite_toggled(self, checked):
        self._dir_edit.setEnabled(not checked)
        self._browse_btn.setEnabled(not checked)
        self._dir_label.setEnabled(not checked)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get(_KEY_OUTPUT_DIR, "Output folder"))
        if folder:
            self._dir_edit.setText(folder)

    def _make_worker(self, output_dir, overwrite, settings):
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            return _SubprocessBatchWorker(
                python, sp, self._paths, output_dir,
                settings["bs"], settings["pad"], overwrite,
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"], shape=settings["shape"])
        return _BatchWorker(
            self._paths, output_dir, settings["bs"], settings["pad"], overwrite,
            mode=settings["mode"], confidence=settings["conf"],
            expand_pct=settings["expand"], style=settings["style"],
            categories=settings["categories"], shape=settings["shape"])

    def _do_run(self):
        overwrite = self._overwrite_check.isChecked()
        output_dir = self._dir_edit.text().strip()
        if not overwrite and (not output_dir or not Path(output_dir).is_dir()):
            return
        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))
        settings = self._collect_settings()

        def _on_deps_ready():
            self._progress.setVisible(True)
            self._progress.setMaximum(len(self._paths))
            self._progress.setValue(0)
            self._status_label.setText("")
            self._worker = self._make_worker(output_dir, overwrite, settings)
            self._worker.progress.connect(self._on_progress)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=settings["mode"],
                     precise=(settings["shape"] == SHAPE_PRECISE))

    def _on_progress(self, current, total, name, *time_args):
        self._progress.setValue(current)
        self._status_label.setText(f"{current + 1}/{total}  {name}")
        self._render_time(current, time_args)

    def _on_finished(self, success, failed, total_regions):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._time_label.setText("")
        msg = _format_result_message(self._lang, success, failed, total_regions)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            toast = self._gui.main_window.toast
            (toast.info if failed else toast.success)(msg)

        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)
        QTimer.singleShot(500, self.accept)
