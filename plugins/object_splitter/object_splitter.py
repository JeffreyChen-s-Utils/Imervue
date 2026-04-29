"""
Object Splitter Plugin
Remove background, detect individual objects via connected components,
and save each object as a separate PNG with transparency.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QLineEdit, QProgressBar,
    QSpinBox, QGroupBox, QMenu,
)

from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.app_paths import is_frozen as _is_frozen

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.object_splitter")

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_runner.py"
_MODELS_DIR = _PLUGIN_DIR / "models"

REQUIRED_PACKAGES = [
    ("rembg", "rembg"),
    ("onnxruntime", "onnxruntime"),
]

MODELS = [
    "u2net", "u2netp", "u2net_human_seg",
    "silueta", "isnet-general-use", "isnet-anime",
]

MODEL_DESCRIPTIONS = {
    "u2net": "General purpose (173 MB)",
    "u2netp": "Lightweight (4 MB, faster)",
    "u2net_human_seg": "Human segmentation",
    "silueta": "General purpose (compact)",
    "isnet-general-use": "IS-Net general (high quality)",
    "isnet-anime": "IS-Net anime/illustration",
}


# ===========================
# Workers
# ===========================

def _subprocess_kwargs() -> dict:
    kw: dict = {
        "stdin": subprocess.DEVNULL,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kw


class _SubprocessWorker(QThread):
    """Run object splitting in an external Python process (frozen env)."""
    step = Signal(int, int, str)  # current, total, message
    result_ready = Signal(bool, str)  # (success, message)

    def __init__(self, python: str, site_packages: str,
                 input_path: str, output_dir: str,
                 model_name: str, min_area: int, padding: int):
        super().__init__()
        self._python = python
        self._site_packages = site_packages
        self._input = input_path
        self._output_dir = output_dir
        self._model = model_name
        self._min_area = min_area
        self._padding = padding

    def run(self):
        try:
            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._site_packages,
                self._input, self._output_dir, self._model,
                str(self._min_area), str(self._padding), str(_MODELS_DIR),
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **_subprocess_kwargs(),
            )
            for line in proc.stdout:
                line = line.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("STEP:"):
                    parts = line[5:].split(":", 2)
                    if len(parts) == 3:
                        self.step.emit(int(parts[0]), int(parts[1]), parts[2])
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
                self.result_ready.emit(True, "0")
        except Exception as exc:
            logger.error("_SubprocessWorker failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc))


class _InProcessWorker(QThread):
    """Run object splitting in-process (dev env)."""
    step = Signal(int, int, str)  # current, total, message
    result_ready = Signal(bool, str)

    def __init__(self, input_path: str, output_dir: str,
                 model_name: str, min_area: int, padding: int):
        super().__init__()
        self._input = input_path
        self._output_dir = output_dir
        self._model = model_name
        self._min_area = min_area
        self._padding = padding

    def run(self):
        try:
            import numpy as np
            from PIL import Image

            _MODELS_DIR.mkdir(parents=True, exist_ok=True)
            os.environ["U2NET_HOME"] = str(_MODELS_DIR)

            self.step.emit(0, 4, "Loading rembg...")
            from rembg import remove, new_session

            self.step.emit(1, 4, f"Loading model: {self._model}...")
            session = new_session(self._model)

            self.step.emit(2, 4, "Removing background...")
            input_img = Image.open(self._input).convert("RGBA")
            output_img = remove(input_img, session=session)

            self.step.emit(3, 4, "Finding objects...")
            alpha = np.array(output_img)[:, :, 3]

            try:
                from scipy.ndimage import label as scipy_label
                labels, num = scipy_label(alpha > 128)
            except ImportError:
                labels, num = _connected_components(alpha > 128)

            # Collect valid objects
            valid = []
            for label_id in range(1, num + 1):
                mask = labels == label_id
                if int(mask.sum()) >= self._min_area:
                    valid.append(label_id)

            total_objects = len(valid)
            self.step.emit(4, 4,
                           f"Found {total_objects} object(s) (filtered from {num} regions)")

            if total_objects == 0:
                self.result_ready.emit(True, "0")
                return

            stem = Path(self._input).stem
            arr = np.array(output_img)
            h, w = alpha.shape

            for i, label_id in enumerate(valid):
                mask = labels == label_id

                ys, xs = np.where(mask)
                y0, y1 = int(ys.min()), int(ys.max()) + 1
                x0, x1 = int(xs.min()), int(xs.max()) + 1

                y0 = max(0, y0 - self._padding)
                x0 = max(0, x0 - self._padding)
                y1 = min(h, y1 + self._padding)
                x1 = min(w, x1 + self._padding)

                cropped = arr[y0:y1, x0:x1].copy()
                crop_mask = mask[y0:y1, x0:x1]
                cropped[~crop_mask, 3] = 0

                obj_img = Image.fromarray(cropped, "RGBA")
                obj_num = i + 1
                out_name = f"{stem}_obj{obj_num}.png"
                out_path = Path(self._output_dir) / out_name
                counter = 1
                while out_path.exists():
                    out_name = f"{stem}_obj{obj_num}_{counter}.png"
                    out_path = Path(self._output_dir) / out_name
                    counter += 1

                obj_img.save(str(out_path))
                self.step.emit(i + 1, total_objects, f"Saved: {out_name}")

            self.result_ready.emit(True, str(total_objects))
        except Exception as exc:
            logger.error("InProcessWorker failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc))


def _connected_components(binary):
    """Simple BFS connected component labeling (no scipy needed)."""
    import numpy as np
    from collections import deque

    h, w = binary.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current_label = 0

    for y in range(h):
        for x in range(w):
            if binary[y, x] and labels[y, x] == 0:
                current_label += 1
                queue = deque()
                queue.append((y, x))
                labels[y, x] = current_label
                while queue:
                    cy, cx = queue.popleft()
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = current_label
                            queue.append((ny, nx))

    return labels, current_label


# ===========================
# Dialog
# ===========================

class ObjectSplitterDialog(QDialog):

    def __init__(self, main_gui: GPUImageView, image_path: str,
                 frozen_env: tuple[str, str] | None = None):
        super().__init__(main_gui.main_window)
        self._gui = main_gui
        self._image_path = image_path
        self._lang = language_wrapper.language_word_dict
        self._worker = None
        self._frozen_env = frozen_env

        self.setWindowTitle(self._lang.get("objsplit_title", "Object Splitter"))
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        lang = self._lang

        layout.addWidget(QLabel(
            lang.get("objsplit_source", "Source:") + f"  {Path(self._image_path).name}"
        ))

        # Model
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel(lang.get("bg_remove_model", "Model:")))
        self._model_combo = QComboBox()
        for m in MODELS:
            desc = MODEL_DESCRIPTIONS.get(m, "")
            self._model_combo.addItem(f"{m}  —  {desc}", m)
        self._model_combo.setCurrentIndex(0)
        model_row.addWidget(self._model_combo, 1)
        layout.addLayout(model_row)

        # Parameters
        params = QGroupBox(lang.get("objsplit_params", "Parameters"))
        play = QHBoxLayout(params)

        play.addWidget(QLabel(lang.get("objsplit_min_area", "Min area (px):")))
        self._min_area = QSpinBox()
        self._min_area.setRange(1, 9999999)
        self._min_area.setValue(500)
        play.addWidget(self._min_area)

        play.addWidget(QLabel(lang.get("objsplit_padding", "Padding (px):")))
        self._padding = QSpinBox()
        self._padding.setRange(0, 500)
        self._padding.setValue(5)
        play.addWidget(self._padding)

        layout.addWidget(params)

        # Output dir
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setText(str(Path(self._image_path).parent))
        browse_btn = QPushButton(lang.get("export_browse", "Browse..."))
        browse_btn.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

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
        cancel_btn = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        self._run_btn = QPushButton(lang.get("objsplit_run", "Split Objects"))
        self._run_btn.clicked.connect(self._do_split)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._lang.get("objsplit_select_folder", "Select Output Folder"))
        if folder:
            self._dir_edit.setText(folder)

    def _do_split(self):
        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self._run_btn.setEnabled(False)
        self._progress_bar.setVisible(True)

        model = self._model_combo.currentData()
        min_area = self._min_area.value()
        padding = self._padding.value()

        if self._frozen_env:
            python, site_pkgs = self._frozen_env
            self._worker = _SubprocessWorker(
                python, site_pkgs, self._image_path, output_dir,
                model, min_area, padding,
            )
        else:
            self._worker = _InProcessWorker(
                self._image_path, output_dir,
                model, min_area, padding,
            )
        self._worker.step.connect(self._on_step)
        self._worker.result_ready.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_step(self, current: int, total: int, msg: str):
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
        self._status_label.setText(msg)

    def _cleanup_worker(self):
        self._worker = None

    def _on_finished(self, success: bool, result: str):
        self._progress_bar.setVisible(False)
        self._run_btn.setEnabled(True)

        lang = self._lang
        if success:
            count = result
            msg = lang.get(
                "objsplit_done", "Done! Extracted {count} object(s)"
            ).format(count=count)
            self._status_label.setText(msg)
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.success(msg)
            # Defer accept so QThread built-in `finished` signal is processed
            # before the dialog is destroyed (avoids use-after-free crash).
            QTimer.singleShot(0, self.accept)
        else:
            self._status_label.setText(f"Error: {result}")
            if hasattr(self._gui.main_window, "toast"):
                self._gui.main_window.toast.info(f"Error: {result}")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(5000)
            self._worker = None
        super().closeEvent(event)


# ===========================
# Plugin
# ===========================

def _ensure_deps(parent, on_ready):
    try:
        ensure_dependencies(parent, REQUIRED_PACKAGES, on_ready)
    except Exception:
        logger.error("_ensure_deps failed", exc_info=True)


class ObjectSplitterPlugin(ImervuePlugin):
    plugin_name = "Object Splitter"
    plugin_version = "1.0.0"
    plugin_description = "Remove background and save each object as a separate image"
    plugin_author = "Imervue"

    def on_build_menu_bar(self, plugin_menu) -> None:
        lang = language_wrapper.language_word_dict
        action = plugin_menu.addAction(
            lang.get("objsplit_title", "Object Splitter"))
        action.triggered.connect(self._open_dialog)

    def on_build_context_menu(self, menu: QMenu, viewer: GPUImageView) -> None:
        if not viewer.deep_zoom:
            return
        images = viewer.model.images
        if not images or viewer.current_index >= len(images):
            return
        lang = language_wrapper.language_word_dict
        path = images[viewer.current_index]
        action = menu.addAction(lang.get("objsplit_title", "Object Splitter"))
        action.triggered.connect(lambda: self._split_image(path))

    def _get_frozen_env(self) -> tuple[str, str] | None:
        if not _is_frozen():
            return None
        from Imervue.plugin.pip_installer import _find_python
        python = _find_python()
        if not python:
            return None
        from Imervue.system.app_paths import app_dir
        site_pkgs = str(app_dir() / "lib" / "site-packages")
        return python, site_pkgs

    def _open_dialog(self):
        images = self.viewer.model.images
        if not images or self.viewer.current_index >= len(images):
            return
        path = images[self.viewer.current_index]
        self._split_image(path)

    def _split_image(self, path: str):
        if not Path(path).is_file():
            return

        def _on_ready():
            try:
                env = self._get_frozen_env()
                dlg = ObjectSplitterDialog(self.viewer, path, frozen_env=env)
                dlg.exec()
            except Exception:
                logger.error("_split_image failed", exc_info=True)

        _ensure_deps(self.main_window, _on_ready)

    def get_translations(self) -> dict[str, dict[str, str]]:
        return {
            "English": {
                "objsplit_title": "Object Splitter",
                "objsplit_source": "Source:",
                "objsplit_params": "Parameters",
                "objsplit_min_area": "Min area (px):",
                "objsplit_padding": "Padding (px):",
                "objsplit_run": "Split Objects",
                "objsplit_select_folder": "Select Output Folder",
                "objsplit_done": "Done! Extracted {count} object(s)",
            },
            "Traditional_Chinese": {
                "objsplit_title": "物件分割",
                "objsplit_source": "來源：",
                "objsplit_params": "參數",
                "objsplit_min_area": "最小面積 (px)：",
                "objsplit_padding": "邊距 (px)：",
                "objsplit_run": "分割物件",
                "objsplit_select_folder": "選擇輸出資料夾",
                "objsplit_done": "完成！擷取了 {count} 個物件",
            },
            "Chinese": {
                "objsplit_title": "对象分割",
                "objsplit_source": "来源：",
                "objsplit_params": "参数",
                "objsplit_min_area": "最小面积 (px)：",
                "objsplit_padding": "边距 (px)：",
                "objsplit_run": "分割对象",
                "objsplit_select_folder": "选择输出文件夹",
                "objsplit_done": "完成！提取了 {count} 个对象",
            },
            "Japanese": {
                "objsplit_title": "オブジェクト分割",
                "objsplit_source": "ソース：",
                "objsplit_params": "パラメータ",
                "objsplit_min_area": "最小面積 (px)：",
                "objsplit_padding": "パディング (px)：",
                "objsplit_run": "オブジェクトを分割",
                "objsplit_select_folder": "出力フォルダを選択",
                "objsplit_done": "完了！{count} 個のオブジェクトを抽出しました",
            },
            "Korean": {
                "objsplit_title": "객체 분할",
                "objsplit_source": "소스:",
                "objsplit_params": "매개변수",
                "objsplit_min_area": "최소 면적 (px):",
                "objsplit_padding": "패딩 (px):",
                "objsplit_run": "객체 분할",
                "objsplit_select_folder": "출력 폴더 선택",
                "objsplit_done": "완료! {count}개의 객체를 추출했습니다",
            },
        }
