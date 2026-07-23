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

from Imervue.plugin.subprocess_util import terminate_process as _terminate_process
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


def _relative_parent(src: str, source_root: str) -> str:
    """Relative subfolder of *src* under *source_root*.

    Returns ``""`` when *src* sits directly inside the root, when no root is
    given, or when *src* lies outside it (different drive / above the root),
    in which case the caller flattens instead of mirroring.
    """
    if not source_root:
        return ""
    try:
        rel = os.path.relpath(str(Path(src).parent), source_root)
    except ValueError:
        return ""  # different drive on Windows — cannot mirror
    if rel == os.curdir or rel.startswith(os.pardir):
        return ""
    return rel


def _mirrored_destination(src: str, output_dir: str, source_root: str) -> str:
    """Non-clobbering destination that mirrors *src*'s position under
    *source_root* into *output_dir*.

    A recursive scan keeps its subfolder tree instead of flattening every
    match into one directory (which would collide same-named images from
    different subfolders). Falls back to a flat destination when *src* is not
    under *source_root*.
    """
    rel_parent = _relative_parent(src, source_root)
    target_dir = Path(output_dir) / rel_parent if rel_parent else Path(output_dir)
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = target_dir / f"{stem}_censored{suffix}"
    counter = 1
    while dst.exists():
        dst = target_dir / f"{stem}_censored_{counter}{suffix}"
        counter += 1
    return str(dst)


def _resolve_destination(src: str, output_dir: str | None, overwrite: bool,
                         source_root: str | None) -> str:
    """Pick the output path for *src*: in-place when overwriting, mirrored
    under *source_root* when set (recursive scan), else flat in *output_dir*."""
    if overwrite:
        return src
    if source_root:
        return _mirrored_destination(src, output_dir, source_root)
    return _non_overwrite_destination(src, output_dir)


def _failed_destination(src: str, failed_dir: str, scan_root: str | None) -> str:
    """Mirrored path for a failed image under *failed_dir*, keeping its name.

    Uses the same relative-parent logic as the output mirror so a failed
    image lands under the failed folder at the same subfolder position it had
    in the scanned tree.
    """
    rel = _relative_parent(src, scan_root or "")
    target_dir = Path(failed_dir) / rel if rel else Path(failed_dir)
    return str(target_dir / Path(src).name)


def _copy_failed(src: str, failed_dir: str, scan_root: str | None) -> None:
    """Copy a failed original into the mirrored failed folder (best-effort)."""
    import shutil
    dst = _failed_destination(src, failed_dir, scan_root)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


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


def _write_failed_manifest(failed_dir: str, failures: list[tuple[str, str]]) -> None:
    """Write a ``censor_failed.log`` listing each failed file and its reason,
    so the user can see *why* each image could not be processed."""
    manifest = Path(failed_dir) / "censor_failed.log"
    with open(manifest, "w", encoding="utf-8") as fh:
        for name, reason in failures:
            fh.write(f"{name}: {reason}\n")


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
                detector, self._input, self._output, self._bs, self._pad,
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
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
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
        detector = _resolve_detector(self._mode)
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
                    detector, _src, _dst, self._bs, self._pad,
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
                 mode: str = MODE_REAL, confidence: float = MIN_CONFIDENCE,
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
