"""Single-image safety_review dialog: settings, one worker, one result."""
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
    _KEY_RUN,
    _ensure_deps,
    _reload_grid_or_deepzoom,
)
from safety_review._dialogs_widgets import _build_mode_row, _SettingsDialogBase
from safety_review._workers import _SingleWorker, _SubprocessSingleWorker


class SafetyReviewDialog(_SettingsDialogBase):
    """Single-image dialog with settings."""

    def __init__(self, main_gui, image_path: str, get_frozen_env=None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._get_frozen_env = get_frozen_env

        self.setWindowTitle(
            self._lang.get("safety_review_title", "Safety Review — Auto Mosaic")
        )
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_output_row(self, layout):
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        stem = Path(self._image_path).stem
        suffix = Path(self._image_path).suffix
        default_out = Path(self._image_path).parent / f"{stem}_censored{suffix}"
        self._path_edit.setText(str(default_out))
        browse_btn = QPushButton(self._lang.get(_KEY_BROWSE, _DEFAULT_BROWSE))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._overwrite_check = QCheckBox(
            self._lang.get("safety_review_overwrite_single",
                           "Overwrite original file"))
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        layout.addWidget(self._overwrite_check)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            self._lang.get("safety_review_source", "Source:")
            + f"  {Path(self._image_path).name}"
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

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, _SingleWorker.STEPS)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%v / %m")
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

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
        if checked:
            self._path_edit.setText(self._image_path)
        self._path_edit.setEnabled(not checked)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._lang.get("export_save", "Save"),
            self._path_edit.text(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
        if path:
            self._path_edit.setText(path)

    def _make_worker(self, output, settings):
        frozen_env = self._get_frozen_env() if self._get_frozen_env else None
        if frozen_env:
            python, sp = frozen_env
            worker = _SubprocessSingleWorker(
                python, sp, self._image_path, output,
                settings["bs"], settings["pad"],
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"], shape=settings["shape"])
            worker.progress.connect(self._on_progress_text)
        else:
            worker = _SingleWorker(
                self._image_path, output, settings["bs"], settings["pad"],
                mode=settings["mode"], confidence=settings["conf"],
                expand_pct=settings["expand"], style=settings["style"],
                categories=settings["categories"], shape=settings["shape"])
            worker.progress.connect(self._on_progress_step)
        return worker

    def _do_run(self):
        output = self._path_edit.text().strip()
        if not output:
            return
        self._run_btn.setEnabled(False)
        self._status_label.setText(
            self._lang.get(_KEY_INSTALLING, _DEFAULT_INSTALLING))
        settings = self._collect_settings()

        def _on_deps_ready():
            self._progress_bar.setVisible(True)
            self._status_label.setText("")
            self._worker = self._make_worker(output, settings)
            self._worker.result_ready.connect(self._on_finished)
            self._worker.finished.connect(self._cleanup)
            self._worker.start()

        _ensure_deps(self._gui.main_window, _on_deps_ready, mode=settings["mode"],
                     precise=(settings["shape"] == SHAPE_PRECISE))

    def _on_progress_step(self, step: int, msg: str):
        """From _SingleWorker (int, str)."""
        self._progress_bar.setValue(step)
        self._status_label.setText(msg)

    def _on_progress_text(self, msg: str):
        """From _SubprocessSingleWorker (str only)."""
        self._status_label.setText(msg)

    def _on_finished(self, ok: bool, result: str, count: int):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)
        if not ok:
            text = self._lang.get("generic_error", "Error: {error}").format(error=result)
            self._status_label.setText(text)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(text)
            return

        if count == 0:
            text = self._lang.get(
                "safety_review_nothing",
                "No genitalia detected — image unchanged.")
        else:
            text = self._lang.get(
                "safety_review_done", "Done! Saved to: {path}"
            ).format(path=result)
        self._status_label.setText(text)
        if hasattr(self._gui.main_window, "toast"):
            self._gui.main_window.toast.success(
                self._lang.get("safety_review_done_short", "Mosaic applied!")
                if count else text)
        if self._overwrite_check.isChecked():
            _reload_grid_or_deepzoom(self._gui)
        QTimer.singleShot(500, self.accept)
