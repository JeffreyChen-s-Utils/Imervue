"""
AI \u53bb\u80cc\u63d2\u4ef6 \u2014 dialogs
Single-image and batch dialogs of the AI Background Remover plugin. Each picks
the subprocess worker when given a frozen environment and the in-process one
otherwise.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QLineEdit, QProgressBar,
    QCheckBox,
)

from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.multi_language.language_wrapper import language_wrapper

from ai_background_remover.ai_background_remover_workers import (
    _BatchRemoveWorker,
    _RemoveBackgroundWorker,
    _SubprocessBatchWorker,
    _SubprocessRemoveWorker,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

MODELS = [
    "u2net", "u2netp", "u2net_human_seg", "u2net_cloth_seg",
    "silueta", "isnet-general-use", "isnet-anime",
]

MODEL_DESCRIPTIONS = {
    "u2net": "General purpose (173 MB)",
    "u2netp": "Lightweight (4 MB, faster)",
    "u2net_human_seg": "Human segmentation",
    "u2net_cloth_seg": "Clothing segmentation",
    "silueta": "General purpose (compact)",
    "isnet-general-use": "IS-Net general (high quality)",
    "isnet-anime": "IS-Net anime/illustration",
}


# ===========================
# \u5c0d\u8a71\u6846
# ===========================

class RemoveBackgroundDialog(WorkerHostMixin, QDialog):

    def __init__(self, main_gui: GPUImageView, image_path: str,
                 frozen_env: tuple[str, str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._frozen_env = frozen_env  # (python_path, site_packages_path)

        self.setWindowTitle(self._lang.get("bg_remove_title", "AI Background Removal"))
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get("bg_remove_source", "Source:") + f"  {Path(self._image_path).name}"
        ))

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(self._lang.get("bg_remove_model", "Model:")))
        self._model_combo = QComboBox()
        for m in MODELS:
            desc = MODEL_DESCRIPTIONS.get(m, "")
            self._model_combo.addItem(f"{m}  \u2014  {desc}", m)
        self._model_combo.setCurrentIndex(0)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        self._alpha_check = QCheckBox(
            self._lang.get("bg_remove_alpha_matting", "Alpha matting (smoother edges, slower)")
        )
        self._alpha_check.setChecked(False)
        layout.addWidget(self._alpha_check)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        default_out = Path(self._image_path).parent / (Path(self._image_path).stem + "_nobg.png")
        self._path_edit.setText(str(default_out))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(self._lang.get("bg_remove_run", "Remove Background"))
        self._run_btn.clicked.connect(self._do_remove)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self._lang.get("export_save", "Save"),
            self._path_edit.text(), "PNG (*.png)",
        )
        if path:
            self._path_edit.setText(path)

    def _do_remove(self):
        output = self._path_edit.text().strip()
        if not output:
            return

        self._run_btn.setEnabled(False)
        self._progress_bar.setVisible(True)

        model = self._model_combo.currentData()
        alpha = self._alpha_check.isChecked()

        if self._frozen_env:
            # Frozen: use subprocess
            python, site_pkgs = self._frozen_env
            self._worker = _SubprocessRemoveWorker(
                python, site_pkgs, self._image_path, output, model, alpha,
            )
        else:
            # Dev: use in-process
            self._worker = _RemoveBackgroundWorker(
                self._image_path, output, model, alpha,
            )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _cleanup_worker(self):
        self._worker = None

    def _on_finished(self, success: bool, result: str):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)

        if success:
            self._status_label.setText(
                self._lang.get("bg_remove_done", "Done! Saved to: {path}").format(path=result)
            )
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(
                    self._lang.get("bg_remove_done_short", "Background removed!")
                )
            QTimer.singleShot(0, self.accept)
        else:
            text = self._lang.get("generic_error", "Error: {error}").format(error=result)
            self._status_label.setText(text)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(text)


class BatchRemoveBackgroundDialog(WorkerHostMixin, QDialog):

    def __init__(self, main_gui: GPUImageView, paths: list[str],
                 frozen_env: tuple[str, str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._frozen_env = frozen_env

        self.setWindowTitle(self._lang.get("bg_remove_batch_title", "Batch AI Background Removal"))
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get("batch_export_count", "{count} image(s) selected").format(
                count=len(self._paths))
        ))

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(self._lang.get("bg_remove_model", "Model:")))
        self._model_combo = QComboBox()
        for m in MODELS:
            desc = MODEL_DESCRIPTIONS.get(m, "")
            self._model_combo.addItem(f"{m}  \u2014  {desc}", m)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        self._alpha_check = QCheckBox(
            self._lang.get("bg_remove_alpha_matting", "Alpha matting (smoother edges, slower)")
        )
        layout.addWidget(self._alpha_check)

        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(self._lang.get("bg_remove_run", "Remove Background"))
        self._run_btn.clicked.connect(self._do_remove)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._dir_edit.setText(folder)

    def _do_remove(self):
        output_dir = self._dir_edit.text().strip()
        if not output_dir or not Path(output_dir).is_dir():
            return

        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._paths))
        self._progress.setValue(0)

        model = self._model_combo.currentData()
        alpha = self._alpha_check.isChecked()

        if self._frozen_env:
            python, site_pkgs = self._frozen_env
            self._worker = _SubprocessBatchWorker(
                python, site_pkgs, self._paths, output_dir, model, alpha,
            )
        else:
            self._worker = _BatchRemoveWorker(
                self._paths, output_dir, model, alpha,
            )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_progress(self, current, total, name):
        self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}  {name}")

    def _cleanup_worker(self):
        self._worker = None

    def _on_finished(self, success, failed):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)

        msg = self._lang.get(
            "bg_remove_batch_done", "Processed {success}/{total} image(s)"
        ).format(success=success, total=success + failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)
        QTimer.singleShot(0, self.accept)
