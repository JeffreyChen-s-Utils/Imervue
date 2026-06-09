"""QThread worker classes for the safety_review plugin.

Two pairs of workers:

* in-process (``_SingleWorker`` / ``_BatchWorker``) run the detector directly
  in the host interpreter, and
* subprocess (``_SubprocessSingleWorker`` / ``_SubprocessBatchWorker``) shell
  out to ``_runner.py`` in an external Python, used in the frozen build where
  the heavy ML deps live in a separate site-packages.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from safety_review._constants import (
    MIN_CONFIDENCE,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    STYLE_MOSAIC,
)
from safety_review._detection import (
    _get_anime_model,
    _get_detector,
    _process_single_image,
    _subprocess_kwargs,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_runner.py"


def _resolve_detector(mode: str):
    """Pre-load the detector(s) for *mode* and return the NudeNet detector
    (or ``None`` for anime-only mode)."""
    if mode == MODE_AUTO:
        detector = _get_detector()
        _get_anime_model()
        return detector
    if mode == MODE_ANIME:
        return None
    return _get_detector()


def _non_overwrite_destination(src: str, output_dir: str) -> str:
    """Build a non-clobbering ``*_censored`` destination path for *src*."""
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = str(Path(output_dir) / f"{stem}_censored{suffix}")
    counter = 1
    while os.path.exists(dst):
        dst = str(Path(output_dir) / f"{stem}_censored_{counter}{suffix}")
        counter += 1
    return dst


class _SingleWorker(QThread):
    """In-process: detect + mosaic a single image."""
    # (step 0-3, step_text)
    progress = Signal(int, str)
    result_ready = Signal(bool, str, int)  # (ok, path_or_error, regions_count)

    STEPS = 3  # load model, detect, save

    def __init__(self, input_path: str, output_path: str,
                 block_size: int, padding: int,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._input = input_path
        self._output = output_path
        self._bs = block_size
        self._pad = padding
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def run(self):
        try:
            self.progress.emit(0, "Loading model...")
            detector = _resolve_detector(self._mode)
            self.progress.emit(1, "Detecting regions...")
            count = _process_single_image(
                detector, self._input, self._output, self._bs, self._pad,
                confidence=self._conf,
                expand_pct=self._expand_pct, mode=self._mode,
                style=self._style, categories=self._categories,
            )
            self.progress.emit(2, "Saving...")
            self.progress.emit(3, "Done")
            self.result_ready.emit(True, self._output, count)
        except Exception as exc:
            logger.error("Single safety review failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc), 0)


class _BatchWorker(QThread):
    """In-process: detect + mosaic a list of images."""
    # (current_idx, total, filename, elapsed_sec, eta_sec)
    progress = Signal(int, int, str, float, float)
    result_ready = Signal(int, int, int)   # (success, failed, total_regions)

    def __init__(self, paths: list[str], output_dir: str | None,
                 block_size: int, padding: int, overwrite: bool,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._paths = paths
        self._output_dir = output_dir
        self._bs = block_size
        self._pad = padding
        self._overwrite = overwrite
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def _destination(self, src: str) -> str:
        if self._overwrite:
            return src
        return _non_overwrite_destination(src, self._output_dir)

    def run(self):
        detector = _resolve_detector(self._mode)
        success = 0
        failed = 0
        total_regions = 0
        total = len(self._paths)
        t0 = time.monotonic()

        for i, src in enumerate(self._paths):
            name = Path(src).name
            elapsed = time.monotonic() - t0
            eta = elapsed / i * (total - i) if i > 0 else 0.0
            self.progress.emit(i, total, name, elapsed, eta)
            try:
                count = _process_single_image(
                    detector, src, self._destination(src), self._bs, self._pad,
                    confidence=self._conf,
                    expand_pct=self._expand_pct, mode=self._mode,
                    style=self._style, categories=self._categories,
                )
                total_regions += count
                success += 1
            except Exception as exc:
                logger.error("Batch safety review failed for %s: %s", src, exc)
                failed += 1

        self.result_ready.emit(success, failed, total_regions)


def _categories_arg(categories) -> str:
    return ",".join(sorted(categories)) if categories else ""


class _SubprocessSingleWorker(QThread):
    """Frozen-env: run detector in an external Python process."""
    progress = Signal(str)
    result_ready = Signal(bool, str, int)

    def __init__(self, python: str, site_packages: str,
                 input_path: str, output_path: str,
                 block_size: int, padding: int,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._python = python
        self._sp = site_packages
        self._input = input_path
        self._output = output_path
        self._bs = block_size
        self._pad = padding
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def _command(self) -> list[str]:
        return [
            self._python, str(_RUNNER_SCRIPT),
            self._sp, "single",
            self._input, self._output,
            str(self._bs), str(self._pad),
            self._mode, str(self._conf),
            str(self._expand_pct),
            self._style, _categories_arg(self._categories),
        ]

    def _consume(self, proc) -> bool:
        """Drain *proc* stdout. Returns True if a terminal line was seen."""
        for raw in proc.stdout:
            line = raw.rstrip("\n\r")
            if not line:
                continue
            if line.startswith("PROGRESS:"):
                self.progress.emit(line[9:])
            elif line.startswith("OK:"):
                self.result_ready.emit(True, line[3:], -1)
                return True
            elif line.startswith("ERROR:"):
                self.result_ready.emit(False, line[6:], 0)
                return True
        return False

    def run(self):
        try:
            proc = subprocess.Popen(
                self._command(), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, **_subprocess_kwargs(),
            )
            terminated = self._consume(proc)
            proc.wait()
            if terminated:
                return
            if proc.returncode != 0:
                self.result_ready.emit(
                    False, f"Process exited with code {proc.returncode}", 0)
            else:
                self.result_ready.emit(True, self._output, -1)
        except Exception as exc:
            logger.error("Subprocess single worker failed: %s", exc, exc_info=True)
            self.result_ready.emit(False, str(exc), 0)


class _SubprocessBatchWorker(QThread):
    """Frozen-env: batch detect in external Python."""
    progress = Signal(int, int, str)
    result_ready = Signal(int, int, int)

    def __init__(self, python: str, site_packages: str,
                 paths: list[str], output_dir: str | None,
                 block_size: int, padding: int, overwrite: bool,
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None):
        super().__init__()
        self._python = python
        self._sp = site_packages
        self._paths = paths
        self._output_dir = output_dir or ""
        self._bs = block_size
        self._pad = padding
        self._overwrite = overwrite
        self._mode = mode
        self._conf = confidence
        self._expand_pct = expand_pct
        self._style = style
        self._categories = categories

    def _command(self, tmp_path: str) -> list[str]:
        return [
            self._python, str(_RUNNER_SCRIPT),
            self._sp, "batch",
            tmp_path, self._output_dir,
            str(self._bs), str(self._pad),
            str(self._overwrite),
            self._mode, str(self._conf),
            str(self._expand_pct),
            self._style, _categories_arg(self._categories),
        ]

    def _emit_progress(self, payload: str) -> None:
        # Protocol: BATCH_PROGRESS:<int>:<int>:<filename>
        # Use maxsplit=2 so colons in filename are preserved.
        parts = payload.split(":", 2)
        if len(parts) == 3:
            with contextlib.suppress(ValueError, RuntimeError):
                self.progress.emit(int(parts[0]), int(parts[1]), parts[2])

    def _emit_ok(self, payload: str) -> None:
        parts = payload.split(":", 1)
        try:
            success, failed = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            success, failed = 0, len(self._paths)
        self.result_ready.emit(success, failed, -1)

    def _consume(self, proc) -> bool:
        """Drain *proc* stdout. Returns True if a terminal line was seen."""
        for raw in proc.stdout:
            line = raw.rstrip("\n\r")
            if not line:
                continue
            if line.startswith("BATCH_PROGRESS:"):
                self._emit_progress(line[15:])
            elif line.startswith("BATCH_OK:"):
                self._emit_ok(line[9:])
                return True
            elif line.startswith("ERROR:"):
                self.result_ready.emit(0, len(self._paths), 0)
                return True
        return False

    def run(self):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            ) as tmp:
                tmp_path = tmp.name
                json.dump(self._paths, tmp)

            proc = subprocess.Popen(
                self._command(tmp_path), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, **_subprocess_kwargs(),
            )
            terminated = self._consume(proc)
            proc.wait()
            if not terminated:
                self.result_ready.emit(0, len(self._paths), 0)
        except Exception as exc:
            logger.error("Subprocess batch worker failed: %s", exc, exc_info=True)
            self.result_ready.emit(0, len(self._paths), 0)
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
