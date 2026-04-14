"""
AI \u53bb\u80cc\u63d2\u4ef6
AI Background Remover \u2014 remove image backgrounds using rembg (U2-Net).

Dependencies are auto-installed on first use via the main app's pip installer.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QLineEdit, QProgressBar,
    QCheckBox, QMenu,
)

from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.app_paths import (
    is_frozen as _is_frozen,
    frozen_site_packages as _frozen_site_packages,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QMenuBar
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.ai_bg_remover")

# \u8a2d\u5b9a\u6a94\u6848\u540d\u7a31\u3001\u7de8\u78bc\u3001\u5c64\u7d1a\u8207\u683c\u5f0f
logging.basicConfig(
    filename='ai_bg_remover.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)

# ===========================
# \u8def\u5f91
# ===========================

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_rembg_runner.py"
logger.info("AI BG Remover: module loading, plugin dir = %s", _PLUGIN_DIR)

# \u6a21\u578b\u5b58\u653e\u5728\u63d2\u4ef6\u76ee\u9304\u4e0b\u7684 models/
_MODELS_DIR = _PLUGIN_DIR / "models"
os.environ["U2NET_HOME"] = str(_MODELS_DIR)
logger.info("AI BG Remover: U2NET_HOME = %s", _MODELS_DIR)

# Frozen \u74b0\u5883 DLL \u8def\u5f91\u8a2d\u5b9a\uff08\u50c5\u4f9b\u975e subprocess \u6a21\u5f0f\u4f7f\u7528\uff09
if _is_frozen():
    logger.info("AI BG Remover: frozen env detected")
    try:
        _site_packages = _frozen_site_packages()
        logger.info("AI BG Remover: site-packages = %s, exists=%s",
                     _site_packages, _site_packages.is_dir())
    except Exception:
        logger.error("AI BG Remover: frozen env setup failed", exc_info=True)

# ===========================
# \u5957\u4ef6\u9700\u6c42
# ===========================

REQUIRED_PACKAGES = [
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
]

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
# Python \u641c\u5c0b\uff08\u51cd\u7d50\u74b0\u5883\u7528\uff09
# ===========================

def _find_external_python() -> str | None:
    """Find the external Python used by pip_installer (cached)."""
    from Imervue.plugin.pip_installer import _find_python
    return _find_python()


def _subprocess_kwargs() -> dict:
    """subprocess \u5171\u7528\u53c3\u6578"""
    kw: dict = {
        "stdin": subprocess.DEVNULL,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kw


# ===========================
# Subprocess Workers (\u51cd\u7d50\u74b0\u5883)
# ===========================

class _SubprocessRemoveWorker(QThread):
    """Runs rembg in an external Python process — safe in frozen builds."""
    progress = Signal(str)
    result_ready = Signal(bool, str)

    def __init__(self, python: str, site_packages: str,
                 input_path: str, output_path: str,
                 model_name: str, alpha_matting: bool):
        super().__init__()
        self._python = python
        self._site_packages = site_packages
        self._input = input_path
        self._output = output_path
        self._model = model_name
        self._alpha_matting = alpha_matting

    def run(self):
        try:
            logger.info("_SubprocessRemoveWorker: starting, python=%s, site_packages=%s",
                         self._python, self._site_packages)
            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._site_packages, "single",
                self._input, self._output, self._model,
                str(self._alpha_matting), str(_MODELS_DIR),
            ]
            kw = _subprocess_kwargs()
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw,
            )
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                logger.info("_SubprocessRemoveWorker: %s", line)
                if line.startswith("PROGRESS:"):
                    self.progress.emit(line[9:])
                elif line.startswith("OK:"):
                    self.result_ready.emit(True, line[3:])
                    proc.wait()
                    return
                elif line.startswith("ERROR:"):
                    self.result_ready.emit(False, line[6:])
                    proc.wait()
                    return

            proc.wait()
            if proc.returncode != 0:
                self.result_ready.emit(False, f"Process exited with code {proc.returncode}")
            else:
                # Shouldn't reach here if protocol is correct
                self.result_ready.emit(True, self._output)
        except Exception as exc:
            logger.error("_SubprocessRemoveWorker failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc))


class _SubprocessBatchWorker(QThread):
    """Runs batch rembg in an external Python process."""
    progress = Signal(int, int, str)
    result_ready = Signal(int, int)

    def __init__(self, python: str, site_packages: str,
                 paths: list[str], output_dir: str,
                 model_name: str, alpha_matting: bool):
        super().__init__()
        self._python = python
        self._site_packages = site_packages
        self._paths = paths
        self._output_dir = output_dir
        self._model = model_name
        self._alpha_matting = alpha_matting

    def run(self):
        tmp_path = None
        try:
            # Write paths to temp file
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            )
            tmp_path = tmp.name
            json.dump(self._paths, tmp)
            tmp.close()

            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._site_packages, "batch",
                tmp_path, self._output_dir, self._model,
                str(self._alpha_matting), str(_MODELS_DIR),
            ]
            kw = _subprocess_kwargs()
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw,
            )
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("BATCH_PROGRESS:"):
                    parts = line[15:].split(":", 2)
                    if len(parts) == 3:
                        try:
                            self.progress.emit(
                                int(parts[0]), int(parts[1]), parts[2])
                        except (ValueError, RuntimeError):
                            pass
                elif line.startswith("BATCH_OK:"):
                    parts = line[9:].split(":", 1)
                    try:
                        self.result_ready.emit(int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        self.result_ready.emit(0, len(self._paths))
                    proc.wait()
                    return
                elif line.startswith("ERROR:"):
                    self.result_ready.emit(0, len(self._paths))
                    proc.wait()
                    return

            proc.wait()
            self.result_ready.emit(0, len(self._paths))
        except Exception as exc:
            logger.error("_SubprocessBatchWorker failed: %s", exc, exc_info=True)
            self.result_ready.emit(0, len(self._paths))
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# ===========================
# In-process Workers (\u958b\u767c\u74b0\u5883)
# ===========================

class _RemoveBackgroundWorker(QThread):
    progress = Signal(str)
    result_ready = Signal(bool, str)

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
            self.result_ready.emit(True, self._output)
        except Exception as exc:
            logger.error("Background removal failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc))

    @staticmethod
    def _load_image(path: str):
        return _load_image_for_rembg(path)


def _load_image_for_rembg(path: str):
    """Load image for rembg, handling SVG via the app's SVG loader."""
    from PIL import Image
    if Path(path).suffix.lower() == ".svg":
        from Imervue.gpu_image_view.images.image_loader import _load_svg
        arr = _load_svg(path, thumbnail=False)
        return Image.fromarray(arr)
    return Image.open(path)


class _BatchRemoveWorker(QThread):
    progress = Signal(int, int, str)
    result_ready = Signal(int, int)

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

        session = new_session(self._model)
        success = 0
        failed = 0
        total = len(self._paths)

        for i, src in enumerate(self._paths):
            try:
                self.progress.emit(i, total, Path(src).name)

                input_img = _load_image_for_rembg(src)

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
                logger.error("Batch bg removal failed for %s: %s", src, exc)
                failed += 1

        self.result_ready.emit(success, failed)


# ===========================
# \u5c0d\u8a71\u6846
# ===========================

class RemoveBackgroundDialog(QDialog):

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
            self._status_label.setText(f"Error: {result}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {result}")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


class BatchRemoveBackgroundDialog(QDialog):

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

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


# ===========================
# Plugin \u672c\u9ad4
# ===========================

def _ensure_deps(parent, on_ready):
    logger.info("_ensure_deps called")
    try:
        ensure_dependencies(parent, REQUIRED_PACKAGES, on_ready)
        logger.info("_ensure_deps: ensure_dependencies returned (async started)")
    except Exception:
        logger.error("_ensure_deps: ensure_dependencies raised", exc_info=True)


class AIBackgroundRemoverPlugin(ImervuePlugin):
    plugin_name = "AI Background Remover"
    plugin_version = "1.2.0"
    plugin_description = "Remove image backgrounds using AI (rembg / U2-Net)"
    plugin_author = "Imervue"

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        self._menu = plugin_menu.addMenu(lang.get("bg_remove_menu", "AI Tools"))

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

    def _get_frozen_env(self) -> tuple[str, str] | None:
        """In frozen mode, find external Python and site-packages path.

        Returns (python_path, site_packages_path) or None in dev mode.
        """
        if not _is_frozen():
            return None
        python = _find_external_python()
        if not python:
            logger.error("No external Python found for subprocess")
            return None
        site_pkgs = str(_frozen_site_packages())
        logger.info("Frozen env: python=%s, site_packages=%s", python, site_pkgs)
        return python, site_pkgs

    def _open_single_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._remove_single(path)

    def _remove_single(self, path: str):
        logger.info("_remove_single called, path=%s", path)
        if not Path(path).is_file():
            return

        def _on_ready():
            logger.info("_remove_single on_ready fired")
            try:
                env = self._get_frozen_env()
                dlg = RemoveBackgroundDialog(self.viewer, path, frozen_env=env)
                logger.info("_remove_single: dialog created, calling exec()")
                dlg.exec()
                logger.info("_remove_single: dialog exec() returned")
            except Exception:
                logger.error("_remove_single: failed", exc_info=True)

        _ensure_deps(self.main_window, _on_ready)

    def _open_batch_dialog(self):
        if (self.viewer.tile_grid_mode and self.viewer.tile_selection_mode
                and self.viewer.selected_tiles):
            paths = list(self.viewer.selected_tiles)
        else:
            paths = list(self.viewer.model.images)
        if paths:
            self._remove_batch(paths)

    def _remove_batch(self, paths: list[str]):
        logger.info("_remove_batch called, %d paths", len(paths))

        def _on_ready():
            logger.info("_remove_batch on_ready fired")
            try:
                env = self._get_frozen_env()
                dlg = BatchRemoveBackgroundDialog(self.viewer, paths, frozen_env=env)
                logger.info("_remove_batch: dialog created, calling exec()")
                dlg.exec()
                logger.info("_remove_batch: dialog exec() returned")
            except Exception:
                logger.error("_remove_batch: failed", exc_info=True)

        _ensure_deps(self.main_window, _on_ready)

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
