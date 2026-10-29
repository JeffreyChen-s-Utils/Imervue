"""
AI \u53bb\u80cc\u63d2\u4ef6 \u2014 workers
Background-removal workers of the AI Background Remover plugin: the subprocess
pair that runs ``_rembg_runner.py`` in an external Python (frozen builds) and the
in-process pair that calls rembg directly (development runs). Also owns the
plugin's runner/model paths and points rembg's ``U2NET_HOME`` at ``models/``.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from Imervue.plugin.pip_installer import _subprocess_kwargs
from Imervue.plugin.model_dir import ensure_model_dir
from Imervue.plugin.subprocess_util import terminate_process

logger = logging.getLogger("Imervue.plugin.ai_bg_remover")

# ===========================
# \u8def\u5f91
# ===========================

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_rembg_runner.py"
logger.info("AI BG Remover: module loading, plugin dir = %s", _PLUGIN_DIR)

# \u6a21\u578b\u5b58\u653e\u5728\u63d2\u4ef6\u76ee\u9304\u4e0b\u7684 models/\u3002Created at import time so the user
# can find the folder in their file manager and drop weights in.
_MODELS_DIR = ensure_model_dir(_PLUGIN_DIR / "models")
os.environ["U2NET_HOME"] = str(_MODELS_DIR)
logger.info("AI BG Remover: U2NET_HOME = %s", _MODELS_DIR)


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
        self._proc = None

    def stop(self):
        """Terminate the child process so a cancelled worker's run loop (blocked
        reading the child's stdout) unblocks and wait() returns promptly."""
        terminate_process(self._proc)

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
            self._proc = proc
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n\r")
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
        self._proc = None

    def stop(self):
        """Terminate the child process so a cancelled worker's run loop (blocked
        reading the child's stdout) unblocks and wait() returns promptly."""
        terminate_process(self._proc)

    def run(self):
        list_path = None
        try:
            # Hand the path list to the child through a temp file.
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            ) as tmp:
                list_path = tmp.name
                json.dump(self._paths, tmp)

            cmd = [
                self._python, str(_RUNNER_SCRIPT),
                self._site_packages, "batch",
                list_path, self._output_dir, self._model,
                str(self._alpha_matting), str(_MODELS_DIR),
            ]
            kw = _subprocess_kwargs()
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw,
            )
            self._proc = proc
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n\r")
                if not line:
                    continue
                if line.startswith("BATCH_PROGRESS:"):
                    parts = line[15:].split(":", 2)
                    if len(parts) == 3:
                        self.progress.emit(int(parts[0]), int(parts[1]), parts[2])
                elif line.startswith("BATCH_OK:"):
                    parts = line[9:].split(":")
                    self.result_ready.emit(int(parts[0]), int(parts[1]))
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
            # Removed on every path, including a Popen that never started.
            if list_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(list_path)


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
        from PIL import Image, ImageOps
        if Path(path).suffix.lower() == ".svg":
            from Imervue.gpu_image_view.images.image_loader import _load_svg
            arr = _load_svg(path, thumbnail=False)
            return Image.fromarray(arr)
        # Upright, as the viewer shows it: the cut-out is saved without EXIF.
        return ImageOps.exif_transpose(Image.open(path))


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
        try:
            _MODELS_DIR.mkdir(parents=True, exist_ok=True)
            from rembg import remove, new_session
            session = new_session(self._model)   # downloads the model on first use
        except Exception:  # a worker must always report: no network, no onnxruntime
            logger.exception("Loading the background-removal model %s failed", self._model)
            self.result_ready.emit(0, len(self._paths))
            return
        from PIL import Image, ImageOps

        success = 0
        failed = 0
        total = len(self._paths)

        for i, src in enumerate(self._paths):
            if self.isInterruptionRequested():
                break
            try:
                self.progress.emit(i, total, Path(src).name)

                if Path(src).suffix.lower() == ".svg":
                    from Imervue.gpu_image_view.images.image_loader import _load_svg
                    arr = _load_svg(src, thumbnail=False)
                    input_img = Image.fromarray(arr)
                else:
                    input_img = ImageOps.exif_transpose(Image.open(src))

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
            except Exception as exc:  # noqa: BLE001 - rembg/onnx fail in any way; log, go on
                logger.error("Batch bg removal failed for %s: %s", src, exc)
                failed += 1

        self.result_ready.emit(success, failed)
