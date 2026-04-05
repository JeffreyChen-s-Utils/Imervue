"""
AI \u53bb\u80cc\u63d2\u4ef6
AI Background Remover \u2014 remove image backgrounds using rembg (U2-Net).

Dependencies are auto-installed on first use via the main app's pip installer.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QLineEdit, QProgressBar,
    QCheckBox, QMenu,
)

from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenuBar
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_bg_remover")

# ===========================
# Frozen \u74b0\u5883 DLL / \u6a21\u578b\u8def\u5f91\u4fee\u6b63
# ===========================

_PLUGIN_DIR = Path(__file__).resolve().parent

# \u6a21\u578b\u5b58\u653e\u5728\u63d2\u4ef6\u76ee\u9304\u4e0b\u7684 models/\uff08\u50c5\u5728\u5be6\u969b\u4e0b\u8f09\u6642\u624d\u5efa\u7acb\uff09
_MODELS_DIR = _PLUGIN_DIR / "models"
os.environ["U2NET_HOME"] = str(_MODELS_DIR)

# \u5728 frozen \u74b0\u5883\u4e0b\uff0connxruntime \u7684 native DLLs \u53ef\u80fd\u5728 lib/site-packages \u88e1\uff0c
# \u9700\u8981\u52a0\u5165 DLL \u641c\u5c0b\u8def\u5f91\uff0c\u5426\u5247\u6703 ImportError / DLL load failed
if getattr(sys, "frozen", False):
    from Imervue.system.app_paths import app_dir as _app_dir
    _site_packages = _app_dir() / "lib" / "site-packages"
    if _site_packages.is_dir():
        # Python 3.8+ \u7684 os.add_dll_directory \u53ef\u7cbe\u78ba\u52a0\u5165 DLL \u641c\u5c0b\u8def\u5f91
        if hasattr(os, "add_dll_directory"):
            # onnxruntime \u7684 DLLs \u901a\u5e38\u5728 onnxruntime/capi/ \u4e0b
            _ort_capi = _site_packages / "onnxruntime" / "capi"
            if _ort_capi.is_dir():
                os.add_dll_directory(str(_ort_capi))
            os.add_dll_directory(str(_site_packages))
        # \u540c\u6642\u52a0\u5165 PATH \u4f5c\u70ba fallback
        os.environ["PATH"] = str(_site_packages) + os.pathsep + os.environ.get("PATH", "")

# ===========================
# \u5957\u4ef6\u9700\u6c42\u5b9a\u7fa9
# ===========================

REQUIRED_PACKAGES = [
    # (import_name, pip_name)
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
]

# rembg \u652f\u63f4\u7684\u6a21\u578b
MODELS = [
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "u2net_cloth_seg",
    "silueta",
    "isnet-general-use",
    "isnet-anime",
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
# \u53bb\u80cc Workers
# ===========================

class _RemoveBackgroundWorker(QThread):
    """\u80cc\u666f\u57f7\u884c\u7dd2\u8655\u7406\u53bb\u80cc"""
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, input_path: str, output_path: str, model_name: str,
                 alpha_matting: bool):
        super().__init__()
        self._input = input_path
        self._output = output_path
        self._model = model_name
        self._alpha_matting = alpha_matting

    def run(self):
        try:
            self.progress.emit("Loading rembg...")
            _MODELS_DIR.mkdir(parents=True, exist_ok=True)
            from rembg import remove, new_session

            self.progress.emit(f"Loading model: {self._model}...")
            session = new_session(self._model)

            self.progress.emit("Processing image...")
            from PIL import Image
            input_img = self._load_image(self._input)

            output_img = remove(
                input_img,
                session=session,
                alpha_matting=self._alpha_matting,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10,
            )

            self.progress.emit("Saving result...")
            output_img.save(self._output)

            self.finished.emit(True, self._output)
        except Exception as exc:
            logger.error(f"Background removal failed: {exc}")
            self.finished.emit(False, str(exc))

    @staticmethod
    def _load_image(path: str):
        from PIL import Image
        if Path(path).suffix.lower() == ".svg":
            from Imervue.gpu_image_view.images.image_loader import _load_svg
            arr = _load_svg(path, thumbnail=False)
            return Image.fromarray(arr)
        return Image.open(path)


class _BatchRemoveWorker(QThread):
    """\u6279\u6b21\u53bb\u80cc"""
    progress = Signal(int, int, str)
    finished = Signal(int, int)

    def __init__(self, paths: list[str], output_dir: str, model_name: str,
                 alpha_matting: bool):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._model = model_name
        self._alpha_matting = alpha_matting

    def run(self):
        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
        from rembg import remove, new_session
        from PIL import Image

        session = new_session(self._model)
        success = 0
        failed = 0
        total = len(self._paths)

        for i, src in enumerate(self._paths):
            try:
                self.progress.emit(i, total, Path(src).name)

                if Path(src).suffix.lower() == ".svg":
                    from Imervue.gpu_image_view.images.image_loader import _load_svg
                    arr = _load_svg(src, thumbnail=False)
                    input_img = Image.fromarray(arr)
                else:
                    input_img = Image.open(src)

                output_img = remove(
                    input_img,
                    session=session,
                    alpha_matting=self._alpha_matting,
                    alpha_matting_foreground_threshold=240,
                    alpha_matting_background_threshold=10,
                    alpha_matting_erode_size=10,
                )

                out_name = Path(src).stem + "_nobg.png"
                out_path = Path(self._output_dir) / out_name
                counter = 1
                while out_path.exists():
                    out_name = f"{Path(src).stem}_nobg_{counter}.png"
                    out_path = Path(self._output_dir) / out_name
                    counter += 1

                output_img.save(str(out_path))
                success += 1
            except Exception as exc:
                logger.error(f"Batch bg removal failed for {src}: {exc}")
                failed += 1

        self.finished.emit(success, failed)


# ===========================
# \u5c0d\u8a71\u6846
# ===========================

class RemoveBackgroundDialog(QDialog):
    """\u55ae\u5f35\u5716\u7247\u53bb\u80cc\u5c0d\u8a71\u6846"""

    def __init__(self, main_gui: GPUImageView, image_path: str):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(self._lang.get("bg_remove_title", "AI Background Removal"))
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Source
        layout.addWidget(QLabel(
            self._lang.get("bg_remove_source", "Source:") + f"  {Path(self._image_path).name}"
        ))

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(self._lang.get("bg_remove_model", "Model:")))
        self._model_combo = QComboBox()
        for m in MODELS:
            desc = MODEL_DESCRIPTIONS.get(m, "")
            self._model_combo.addItem(f"{m}  \u2014  {desc}", m)
        self._model_combo.setCurrentIndex(0)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        # Alpha matting
        self._alpha_check = QCheckBox(
            self._lang.get("bg_remove_alpha_matting", "Alpha matting (smoother edges, slower)")
        )
        self._alpha_check.setChecked(False)
        layout.addWidget(self._alpha_check)

        # Output path
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        default_out = Path(self._image_path).parent / (Path(self._image_path).stem + "_nobg.png")
        self._path_edit.setText(str(default_out))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
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
        self._worker = _RemoveBackgroundWorker(
            self._image_path, output, model, self._alpha_check.isChecked()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_finished(self, success: bool, result: str):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)
        self._worker = None

        if success:
            self._status_label.setText(
                self._lang.get("bg_remove_done", "Done! Saved to: {path}").format(path=result)
            )
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(
                    self._lang.get("bg_remove_done_short", "Background removed!")
                )
            self.accept()
        else:
            self._status_label.setText(f"Error: {result}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {result}")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)


class BatchRemoveBackgroundDialog(QDialog):
    """\u6279\u6b21\u53bb\u80cc\u5c0d\u8a71\u6846"""

    def __init__(self, main_gui: GPUImageView, paths: list[str]):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._paths = paths
        self._lang = language_wrapper.language_word_dict
        self._worker = None

        self.setWindowTitle(self._lang.get("bg_remove_batch_title", "Batch AI Background Removal"))
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            self._lang.get("batch_export_count", "{count} image(s) selected").format(
                count=len(self._paths))
        ))

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(self._lang.get("bg_remove_model", "Model:")))
        self._model_combo = QComboBox()
        for m in MODELS:
            desc = MODEL_DESCRIPTIONS.get(m, "")
            self._model_combo.addItem(f"{m}  \u2014  {desc}", m)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        # Alpha matting
        self._alpha_check = QCheckBox(
            self._lang.get("bg_remove_alpha_matting", "Alpha matting (smoother edges, slower)")
        )
        layout.addWidget(self._alpha_check)

        # Output dir
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        if self._paths:
            self._dir_edit.setText(str(Path(self._paths[0]).parent))
        browse_btn = QPushButton(self._lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
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
        self._worker = _BatchRemoveWorker(
            self._paths, output_dir, model, self._alpha_check.isChecked()
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current, total, name):
        self._progress.setValue(current)
        self._status_label.setText(f"{current}/{total}  {name}")

    def _on_finished(self, success, failed):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._worker = None

        msg = self._lang.get(
            "bg_remove_batch_done", "Processed {success}/{total} image(s)"
        ).format(success=success, total=success + failed)
        self._status_label.setText(msg)

        if hasattr(self._gui.main_window, "toast"):
            if failed:
                self._gui.main_window.toast.info(msg)
            else:
                self._gui.main_window.toast.success(msg)
        self.accept()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)


# ===========================
# Plugin \u672c\u9ad4
# ===========================

def _ensure_deps(parent, on_ready):
    """\u900f\u904e\u4e3b\u7a0b\u5f0f\u7684 pip_installer \u78ba\u8a8d\u4f9d\u8cf4"""
    ensure_dependencies(parent, REQUIRED_PACKAGES, on_ready)


class AIBackgroundRemoverPlugin(ImervuePlugin):
    plugin_name = "AI Background Remover"
    plugin_version = "1.1.0"
    plugin_description = "Remove image backgrounds using AI (rembg / U2-Net)"
    plugin_author = "Imervue"

    def on_build_menu_bar(self, menu_bar: QMenuBar) -> None:
        lang = language_wrapper.language_word_dict
        self._menu = menu_bar.addMenu(lang.get("bg_remove_menu", "AI Tools"))

        action = self._menu.addAction(lang.get("bg_remove_title", "AI Background Removal"))
        action.triggered.connect(self._open_single_dialog)

        batch_action = self._menu.addAction(
            lang.get("bg_remove_batch_title", "Batch AI Background Removal")
        )
        batch_action.triggered.connect(self._open_batch_dialog)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        lang = language_wrapper.language_word_dict

        if viewer.deep_zoom:
            images = viewer.model.images
            if images and 0 <= viewer.current_index < len(images):
                path = images[viewer.current_index]
                action = menu.addAction(lang.get("bg_remove_title", "AI Background Removal"))
                action.triggered.connect(lambda: self._remove_single(path))

        if (viewer.tile_grid_mode and viewer.tile_selection_mode
                and viewer.selected_tiles and len(viewer.selected_tiles) >= 1):
            paths = list(viewer.selected_tiles)
            action = menu.addAction(
                lang.get("bg_remove_batch_title", "Batch AI Background Removal")
            )
            action.triggered.connect(lambda: self._remove_batch(paths))

    # ----- \u5165\u53e3\uff1a\u5168\u90e8\u7d93\u904e ensure_dependencies -----

    def _open_single_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._remove_single(path)

    def _remove_single(self, path: str):
        if not Path(path).is_file():
            return
        _ensure_deps(
            self.main_window,
            lambda: RemoveBackgroundDialog(self.viewer, path).exec(),
        )

    def _open_batch_dialog(self):
        if (self.viewer.tile_grid_mode and self.viewer.tile_selection_mode
                and self.viewer.selected_tiles):
            paths = list(self.viewer.selected_tiles)
        else:
            paths = list(self.viewer.model.images)
        if paths:
            self._remove_batch(paths)

    def _remove_batch(self, paths: list[str]):
        _ensure_deps(
            self.main_window,
            lambda: BatchRemoveBackgroundDialog(self.viewer, paths).exec(),
        )

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "bg_remove_menu": "AI Tools",
                "bg_remove_title": "AI Background Removal",
                "bg_remove_batch_title": "Batch AI Background Removal",
                "bg_remove_source": "Source:",
                "bg_remove_model": "Model:",
                "bg_remove_alpha_matting": "Alpha matting (smoother edges, slower)",
                "bg_remove_run": "Remove Background",
                "bg_remove_done": "Done! Saved to: {path}",
                "bg_remove_done_short": "Background removed!",
                "bg_remove_batch_done": "Processed {success}/{total} image(s)",
            },
            "Traditional_Chinese": {
                "bg_remove_menu": "AI \u5de5\u5177",
                "bg_remove_title": "AI \u53bb\u80cc",
                "bg_remove_batch_title": "\u6279\u6b21 AI \u53bb\u80cc",
                "bg_remove_source": "\u4f86\u6e90\uff1a",
                "bg_remove_model": "\u6a21\u578b\uff1a",
                "bg_remove_alpha_matting": "Alpha matting\uff08\u908a\u7de3\u66f4\u5e73\u6ed1\uff0c\u8f03\u6162\uff09",
                "bg_remove_run": "\u53bb\u9664\u80cc\u666f",
                "bg_remove_done": "\u5b8c\u6210\uff01\u5df2\u5132\u5b58\u81f3\uff1a{path}",
                "bg_remove_done_short": "\u53bb\u80cc\u5b8c\u6210\uff01",
                "bg_remove_batch_done": "\u5df2\u8655\u7406 {success}/{total} \u5f35\u5716\u7247",
            },
            "Chinese": {
                "bg_remove_menu": "AI \u5de5\u5177",
                "bg_remove_title": "AI \u53bb\u80cc",
                "bg_remove_batch_title": "\u6279\u91cf AI \u53bb\u80cc",
                "bg_remove_source": "\u6765\u6e90\uff1a",
                "bg_remove_model": "\u6a21\u578b\uff1a",
                "bg_remove_alpha_matting": "Alpha matting\uff08\u8fb9\u7f18\u66f4\u5e73\u6ed1\uff0c\u8f83\u6162\uff09",
                "bg_remove_run": "\u53bb\u9664\u80cc\u666f",
                "bg_remove_done": "\u5b8c\u6210\uff01\u5df2\u4fdd\u5b58\u81f3\uff1a{path}",
                "bg_remove_done_short": "\u53bb\u80cc\u5b8c\u6210\uff01",
                "bg_remove_batch_done": "\u5df2\u5904\u7406 {success}/{total} \u5f20\u56fe\u7247",
            },
            "Japanese": {
                "bg_remove_menu": "AI \u30c4\u30fc\u30eb",
                "bg_remove_title": "AI \u80cc\u666f\u9664\u53bb",
                "bg_remove_batch_title": "\u4e00\u62ec AI \u80cc\u666f\u9664\u53bb",
                "bg_remove_source": "\u30bd\u30fc\u30b9\uff1a",
                "bg_remove_model": "\u30e2\u30c7\u30eb\uff1a",
                "bg_remove_alpha_matting": "\u30a2\u30eb\u30d5\u30a1\u30de\u30c3\u30c6\u30a3\u30f3\u30b0\uff08\u3088\u308a\u6ed1\u3089\u304b\u306a\u5883\u754c\u3001\u4f4e\u901f\uff09",
                "bg_remove_run": "\u80cc\u666f\u3092\u9664\u53bb",
                "bg_remove_done": "\u5b8c\u4e86\uff01\u4fdd\u5b58\u5148\uff1a{path}",
                "bg_remove_done_short": "\u80cc\u666f\u9664\u53bb\u5b8c\u4e86\uff01",
                "bg_remove_batch_done": "{success}/{total} \u679a\u306e\u753b\u50cf\u3092\u51e6\u7406\u3057\u307e\u3057\u305f",
            },
            "Korean": {
                "bg_remove_menu": "AI \ub3c4\uad6c",
                "bg_remove_title": "AI \ubc30\uacbd \uc81c\uac70",
                "bg_remove_batch_title": "\uc77c\uad04 AI \ubc30\uacbd \uc81c\uac70",
                "bg_remove_source": "\uc18c\uc2a4:",
                "bg_remove_model": "\ubaa8\ub378:",
                "bg_remove_alpha_matting": "\uc54c\ud30c \ub9e4\ud305 (\ub354 \ubd80\ub4dc\ub7ec\uc6b4 \uacbd\uacc4, \ub290\ub9bc)",
                "bg_remove_run": "\ubc30\uacbd \uc81c\uac70",
                "bg_remove_done": "\uc644\ub8cc! \uc800\uc7a5 \uc704\uce58: {path}",
                "bg_remove_done_short": "\ubc30\uacbd \uc81c\uac70 \uc644\ub8cc!",
                "bg_remove_batch_done": "{success}/{total}\uac1c\uc758 \uc774\ubbf8\uc9c0\ub97c \ucc98\ub9ac\ud588\uc2b5\ub2c8\ub2e4",
            },
        }
