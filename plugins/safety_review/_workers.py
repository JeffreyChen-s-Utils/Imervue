"""QThread worker classes for the safety_review plugin.

Two pairs of workers:

* in-process (``_SingleWorker`` / ``_BatchWorker``) run the detector directly
  in the host interpreter, and
* subprocess (``_SubprocessSingleWorker`` / ``_SubprocessBatchWorker``, in
  :mod:`_workers_subprocess`) shell out to ``_runner.py`` in an external
  Python, used in the frozen build where the heavy ML deps live in a separate
  site-packages.

The in-process workers' output and failed-folder paths live in
:mod:`_workers_paths`. This module stays the import location for every worker
name: the dialogs and tests import them from here.
"""
from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from safety_review._constants import (
    MIN_CONFIDENCE,
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    SHAPE_ELLIPSE,
    SHAPE_RECT,
    STYLE_MOSAIC,
)
from safety_review._detection import (
    _get_anime_model,
    _get_detector,
    _process_single_image,
)
from safety_review._workers_paths import (
    _copy_failed,
    _failed_destination,
    _mirrored_destination,
    _non_overwrite_destination,
    _relative_parent,
    _resolve_destination,
    _write_failed_manifest,
)
from safety_review._workers_subprocess import (
    _PLUGIN_DIR,
    _RUNNER_SCRIPT,
    _categories_arg,
    _SubprocessBatchWorker,
    _SubprocessSingleWorker,
    _terminate_process,
)

__all__ = [
    "_PLUGIN_DIR",
    "_RUNNER_SCRIPT",
    "_BatchWorker",
    "_SingleWorker",
    "_SubprocessBatchWorker",
    "_SubprocessSingleWorker",
    "_categories_arg",
    "_copy_failed",
    "_failed_destination",
    "_mirrored_destination",
    "_non_overwrite_destination",
    "_process_with_shape_fallback",
    "_relative_parent",
    "_resolve_destination",
    "_resolve_detector",
    "_terminate_process",
    "_write_failed_manifest",
]

logger = logging.getLogger("Imervue.plugin.safety_review")


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


def _process_with_shape_fallback(run_for_shape, shape: str, retries: int = 1):
    """Run *run_for_shape(shape)*, retrying then downgrading to ellipse before
    giving up — so only a genuinely unprocessable image reaches the failed
    folder.

    Order of attempts: the chosen shape ``1 + retries`` times (catches a
    transient read/lock), then one ellipse attempt (a precise/segmentation
    hiccup still yields a censored image rather than a failure). Returns the
    callable's result, or re-raises the last error if every attempt fails.
    """
    attempts = [shape] * (1 + max(0, retries))
    if shape != SHAPE_ELLIPSE:
        attempts.append(SHAPE_ELLIPSE)
    last_exc: Exception | None = None
    for attempt_shape in attempts:
        try:
            return run_for_shape(attempt_shape)
        except Exception as exc:  # noqa: BLE001 — try the next fallback shape
            last_exc = exc
    raise last_exc



class _SingleWorker(QThread):
    """In-process: detect + mosaic a single image."""
    # (step 0-3, step_text)
    progress = Signal(int, str)
    result_ready = Signal(bool, str, int)  # (ok, path_or_error, regions_count)

    STEPS = 3  # load model, detect, save

    def __init__(self, input_path: str, output_path: str,
                 block_size: int, padding: int,
                 *, mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None, shape: str = SHAPE_RECT):
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
        self._shape = shape

    def run(self):
        try:
            self.progress.emit(0, "Loading model...")
            detector = _resolve_detector(self._mode)
            self.progress.emit(1, "Detecting regions...")
            count = _process_single_image(
                detector, self._input, self._output, block_size=self._bs, padding=self._pad,
                confidence=self._conf,
                expand_pct=self._expand_pct, mode=self._mode,
                style=self._style, categories=self._categories,
                shape=self._shape,
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
                 *, mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
                 expand_pct: int = 0, style: str = STYLE_MOSAIC,
                 categories=None, source_root: str | None = None,
                 only_censored: bool = False, shape: str = SHAPE_RECT,
                 failed_dir: str | None = None, scan_root: str | None = None,
                 merge_regions: bool = True):
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
        self._source_root = source_root
        self._only_censored = only_censored
        self._shape = shape
        self._merge_regions = merge_regions
        # Where to collect copies of images that fail to process, mirroring
        # their subfolder under scan_root. None → failures are only counted.
        self._failed_dir = failed_dir
        self._scan_root = scan_root

    def _destination(self, src: str) -> str:
        return _resolve_destination(
            src, self._output_dir, self._overwrite, self._source_root)

    def _record_failure(self, src: str, exc: Exception,
                        failures: list[tuple[str, str]]) -> None:
        """Log the failure, and copy the original into the failed folder."""
        logger.error("Batch safety review failed for %s: %s", src, exc)
        failures.append((Path(src).name, str(exc)))
        if self._failed_dir:
            with contextlib.suppress(OSError):
                _copy_failed(src, self._failed_dir, self._scan_root)

    def run(self):
        try:
            detector = _resolve_detector(self._mode)
        except Exception:  # a worker must always report: the model failed to load
            logger.exception("Loading the %s detector failed", self._mode)
            self.result_ready.emit(0, len(self._paths), 0)
            return
        success = 0
        total_regions = 0
        failures: list[tuple[str, str]] = []
        total = len(self._paths)
        t0 = time.monotonic()

        for i, src in enumerate(self._paths):
            if self.isInterruptionRequested():
                break
            name = Path(src).name
            elapsed = time.monotonic() - t0
            eta = elapsed / i * (total - i) if i > 0 else 0.0
            self.progress.emit(i, total, name, elapsed, eta)
            # Compute the destination once so retries reuse it instead of
            # spawning "_censored_1, _2…" copies for the same source.
            dst = self._destination(src)

            def _run(shp, _src=src, _dst=dst):
                return _process_single_image(
                    detector, _src, _dst, block_size=self._bs, padding=self._pad,
                    confidence=self._conf, expand_pct=self._expand_pct,
                    mode=self._mode, style=self._style,
                    categories=self._categories,
                    only_censored=self._only_censored, shape=shp,
                    merge_regions=self._merge_regions)

            try:
                count = _process_with_shape_fallback(_run, self._shape)
                total_regions += count
                success += 1
            except Exception as exc:  # noqa: BLE001 — one bad image must not abort the batch
                self._record_failure(src, exc, failures)

        if failures and self._failed_dir:
            with contextlib.suppress(OSError):
                _write_failed_manifest(self._failed_dir, failures)

        self.result_ready.emit(success, len(failures), total_regions)
