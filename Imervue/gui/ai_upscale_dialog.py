"""
AI 圖片放大 (Super Resolution)
AI Image Upscale — Real-ESRGAN via ONNX Runtime.

Models are automatically downloaded from HuggingFace on first use.
Dependencies: onnxruntime, huggingface_hub, numpy (all lightweight).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.gui.ai_upscale_dialog_run import UpscaleRunMixin
from Imervue.gui.ai_upscale_engine import (
    REQUIRED_PACKAGES, TRADITIONAL_METHODS, UPSCALE_MODELS, _TILE_PAD, _TILE_SIZE,
    _TRAD_PREFIX, _TRAD_RESAMPLING, _ai_upscale, _download_model, _preferred_providers,
    _scan_folder, _upscale_image, _upscale_tile, fill_upscale_model_combo,
)
from Imervue.gui.ai_upscale_worker import _UpscaleWorker
from Imervue.gui.dialog_rows import action_button_row, folder_picker_row, path_browse_row
from Imervue.plugin.worker_host import WorkerHostMixin
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

# Registry, inference helpers and the worker live in ai_upscale_engine /
# ai_upscale_worker; they stay importable from here for existing callers.
__all__ = [
    "REQUIRED_PACKAGES",
    "TRADITIONAL_METHODS",
    "UPSCALE_MODELS",
    "_TILE_PAD",
    "_TILE_SIZE",
    "_TRAD_PREFIX",
    "_TRAD_RESAMPLING",
    "AIUpscaleDialog",
    "_UpscaleWorker",
    "_ai_upscale",
    "_download_model",
    "_preferred_providers",
    "_scan_folder",
    "_upscale_image",
    "_upscale_tile",
    "fill_upscale_model_combo",
    "open_ai_upscale",
    "open_ai_upscale_batch",
    "open_ai_upscale_single",
]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class AIUpscaleDialog(UpscaleRunMixin, WorkerHostMixin, QDialog):
    def __init__(self, main_gui: GPUImageView,
                 paths: list[str] | None = None,
                 folder: str | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths: list[str] = paths or []
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        # True when paths were supplied externally (single/batch/all);
        # False when the user should pick a source folder themselves.
        self._has_preset_paths = bool(self._paths)

        self.setWindowTitle(
            self._lang.get("upscale_title", "AI Image Upscale"))
        self.setMinimumWidth(520)
        self._build_ui()

        if self._has_preset_paths:
            self._update_count()
        elif folder and os.path.isdir(folder):
            self._src_edit.setText(folder)
            self._rescan_folder()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(self._lang.get(
            "upscale_info",
            "Upscale images using Real-ESRGAN AI model. "
            "Models are downloaded automatically on first use (~65 MB)."))
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(self._build_source_section())

        # Image count
        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        layout.addLayout(self._build_model_row())
        layout.addLayout(self._build_scale_row())
        layout.addWidget(self._build_overwrite_check())
        self._add_output_rows(layout)

        # Progress
        self._progress = QProgressBar()
        self._progress.setFormat("%v / %m  (%p%)")
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._tile_progress = QProgressBar()
        self._tile_progress.setFormat(
            self._lang.get("upscale_tile_progress",
                           "Tile: %v / %m") + "  (%p%)")
        self._tile_progress.setVisible(False)
        layout.addWidget(self._tile_progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addLayout(self._build_button_row())

    def _build_source_section(self) -> QWidget:
        """Source folder row and subfolder toggle; hidden when paths were supplied."""
        self._src_row_widget = QWidget()
        src_layout = QVBoxLayout(self._src_row_widget)
        src_layout.setContentsMargins(0, 0, 0, 0)
        src_layout.setSpacing(4)

        src_row, self._src_edit = folder_picker_row(
            self._lang.get("exif_strip_source", "Source folder:"), self._browse_src,
            browse_text=self._lang.get("export_browse", "Browse..."))
        self._src_edit.textChanged.connect(self._rescan_folder)
        src_layout.addLayout(src_row)

        self._recursive_check = QCheckBox(
            self._lang.get("sanitize_recursive", "Include subfolders"))
        self._recursive_check.toggled.connect(
            lambda _: self._rescan_folder())
        src_layout.addWidget(self._recursive_check)

        if self._has_preset_paths:
            self._src_row_widget.hide()
        return self._src_row_widget

    def _build_model_row(self) -> QHBoxLayout:
        """Method / model combo: traditional methods first, then the AI models."""
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(
            self._lang.get("upscale_model", "Model:")))
        self._model_combo = QComboBox()
        fill_upscale_model_combo(self._model_combo, self._lang)
        self._model_combo.currentIndexChanged.connect(
            self._on_method_changed)
        self._model_combo.setToolTip(self._lang.get(
            "upscale_model_tooltip",
            "AI models reconstruct detail; traditional methods do "
            "high-quality interpolation. AI is slower but recovers "
            "fine texture and edges that resampling can't.",
        ))
        model_row.addWidget(self._model_combo, 1)
        return model_row

    def _build_scale_row(self) -> QHBoxLayout:
        """Scale factor, shown only for the traditional methods."""
        scale_row = QHBoxLayout()
        self._scale_label = QLabel(
            self._lang.get("upscale_scale", "Scale factor:"))
        scale_row.addWidget(self._scale_label)
        self._scale_spin = QSpinBox()
        self._scale_spin.setRange(2, 8)
        self._scale_spin.setValue(2)
        self._scale_spin.setToolTip(self._lang.get(
            "upscale_scale_tooltip",
            "Output multiplier — 2 doubles each side, 4 quadruples, etc.",
        ))
        scale_row.addWidget(self._scale_spin)
        scale_row.addStretch()
        return scale_row

    def _build_overwrite_check(self) -> QCheckBox:
        """Overwrite-in-place toggle; checking it hides the output folder row."""
        self._overwrite_check = QCheckBox(
            self._lang.get("upscale_overwrite",
                           "Overwrite original files"))
        self._overwrite_check.setChecked(False)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        self._overwrite_check.setToolTip(self._lang.get(
            "upscale_overwrite_tooltip",
            "Replace each source file in place. Off (default) writes "
            "to the chosen output folder so the originals are safe.",
        ))
        return self._overwrite_check

    def _add_output_rows(self, layout: QVBoxLayout) -> None:
        """Output label above the path edit + Browse row, prefilled from the first path."""
        self._out_label = QLabel(
            self._lang.get("upscale_output", "Output folder:"))
        layout.addWidget(self._out_label)
        out_row, self._out_edit, self._out_browse = path_browse_row(
            self._browse_out, browse_text=self._lang.get("export_browse", "Browse..."))
        if self._paths:
            self._out_edit.setText(str(Path(self._paths[0]).parent))
        layout.addLayout(out_row)

    def _build_button_row(self) -> QHBoxLayout:
        """Right-aligned Cancel and Upscale; Upscale starts enabled only with paths."""
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._start_btn = QPushButton(
            self._lang.get("upscale_start", "Upscale"))
        self._start_btn.clicked.connect(self._do_start)
        self._start_btn.setEnabled(bool(self._paths))
        return action_button_row(cancel_btn, self._start_btn)

    def _update_count(self):
        count = len(self._paths)
        self._count_label.setText(
            self._lang.get("upscale_count",
                           "{count} image(s)").format(count=count))
        self._start_btn.setEnabled(count > 0)

    def _browse_src(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self._lang.get("main_window_select_folder", "Select Folder"))
        if folder:
            self._src_edit.setText(folder)

    def _rescan_folder(self):
        """Re-scan the source folder and update the paths list."""
        if self._has_preset_paths:
            return
        folder = self._src_edit.text().strip()
        if folder and os.path.isdir(folder):
            recursive = self._recursive_check.isChecked()
            self._paths = _scan_folder(folder, recursive=recursive)
            # Default output dir to source folder
            if not self._out_edit.text().strip():
                self._out_edit.setText(folder)
        else:
            self._paths = []
        self._update_count()

    def _is_traditional(self) -> bool:
        key = self._model_combo.currentData()
        return key is not None and key.startswith(_TRAD_PREFIX)

    def _on_method_changed(self, _index: int):
        trad = self._is_traditional()
        self._scale_label.setVisible(trad)
        self._scale_spin.setVisible(trad)

    def _on_overwrite_toggled(self, checked):
        self._out_label.setVisible(not checked)
        self._out_edit.setVisible(not checked)
        self._out_browse.setVisible(not checked)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("upscale_output", "Output folder"))
        if folder:
            self._out_edit.setText(folder)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def open_ai_upscale(main_gui: GPUImageView):
    """Open upscale dialog with folder selection (pre-fills current folder)."""
    folder = None
    if hasattr(main_gui, "model") and hasattr(main_gui.model, "folder_path"):
        folder = main_gui.model.folder_path
    dlg = AIUpscaleDialog(main_gui, folder=folder)
    dlg.exec()


def open_ai_upscale_single(main_gui: GPUImageView, path: str):
    """Open upscale dialog for a single image."""
    dlg = AIUpscaleDialog(main_gui, paths=[path])
    dlg.exec()


def open_ai_upscale_batch(main_gui: GPUImageView):
    """Open upscale dialog with selected tiles."""
    paths = list(main_gui.selected_tiles) if main_gui.selected_tiles else []
    if not paths:
        return
    dlg = AIUpscaleDialog(main_gui, paths=paths)
    dlg.exec()
