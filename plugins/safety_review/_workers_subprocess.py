"""Subprocess QThread workers for the safety_review plugin.

Used in the frozen build, where the heavy ML deps live in a separate
site-packages: each worker starts ``_runner.py`` in an external Python with a
fixed argv (no shell), reads its stdout protocol (see ``_runner``'s module
docstring) and always ends with one ``result_ready`` unless cancelled.
Re-exported by :mod:`safety_review._workers`.
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
from Imervue.plugin.subprocess_util import terminate_process as _terminate_process
from safety_review._constants import (
    MIN_CONFIDENCE,
    MODE_REAL,
    SHAPE_RECT,
    STYLE_MOSAIC,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

_PLUGIN_DIR = Path(__file__).resolve().parent
_RUNNER_SCRIPT = _PLUGIN_DIR / "_runner.py"


def _categories_arg(categories) -> str:
    return ",".join(sorted(categories)) if categories else ""


class _SubprocessSingleWorker(QThread):
    """Frozen-env: run detector in an external Python process."""
    progress = Signal(str)
    result_ready = Signal(bool, str, int)

    def __init__(self, python: str, site_packages: str,
                 input_path: str, output_path: str,
                 block_size: int, padding: int,
                 *, mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None, shape: str = SHAPE_RECT):
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
        self._shape = shape

    def _command(self) -> list[str]:
        return [
            self._python, str(_RUNNER_SCRIPT),
            self._sp, "single",
            self._input, self._output,
            str(self._bs), str(self._pad),
            self._mode, str(self._conf),
            str(self._expand_pct),
            self._style, _categories_arg(self._categories),
            self._shape,
        ]

    def _consume(self, proc) -> bool:
        """Drain *proc* stdout. Returns True if a terminal line was seen."""
        for raw in proc.stdout:
            if self.isInterruptionRequested():
                _terminate_process(proc)
                return True
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
        proc = None
        try:
            proc = subprocess.Popen(  # nosec B603,B607  # nosemgrep
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
        finally:
            _terminate_process(proc)


class _SubprocessBatchWorker(QThread):
    """Frozen-env: batch detect in external Python."""
    progress = Signal(int, int, str)
    result_ready = Signal(int, int, int)

    def __init__(self, python: str, site_packages: str,
                 paths: list[str], output_dir: str | None,
                 block_size: int, padding: int, overwrite: bool,
                 *, mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None, source_root: str | None = None,
                 only_censored: bool = False, shape: str = SHAPE_RECT,
                 failed_dir: str | None = None, scan_root: str | None = None,
                 merge_regions: bool = True):
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
        self._source_root = source_root or ""
        self._only_censored = only_censored
        self._shape = shape
        self._failed_dir = failed_dir or ""
        self._scan_root = scan_root or ""
        self._merge_regions = merge_regions

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
            self._source_root, str(self._only_censored), self._shape,
            self._failed_dir, self._scan_root, str(self._merge_regions),
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
            if self.isInterruptionRequested():
                _terminate_process(proc)
                return True
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
        proc = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8",
            ) as tmp:
                tmp_path = tmp.name
                json.dump(self._paths, tmp)

            proc = subprocess.Popen(  # nosec B603,B607  # nosemgrep
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
            _terminate_process(proc)
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
