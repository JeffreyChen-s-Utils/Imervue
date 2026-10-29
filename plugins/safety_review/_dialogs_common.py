"""Shared helpers for the safety_review dialogs.

The dependency gate (``_ensure_deps``), duration / summary formatting, the
host-viewer refresh after an in-place write, the repeated language keys, and
``_WorkerHostMixin`` (progress-time rendering plus the worker teardown every
dialog runs on Cancel / Escape / close).
"""
from __future__ import annotations

import contextlib
import logging

from Imervue.plugin.pip_installer import ensure_dependencies

from safety_review._constants import (
    MODE_ANIME,
    MODE_AUTO,
    MODE_REAL,
    REQUIRED_PACKAGES_ANIME,
    REQUIRED_PACKAGES_AUTO,
    REQUIRED_PACKAGES_PRECISE,
    REQUIRED_PACKAGES_REAL,
)

logger = logging.getLogger("Imervue.plugin.safety_review")

# Repeated language-key constants (declared once — SonarQube python:S1192).
_KEY_BROWSE = "export_browse"
_KEY_CANCEL = "export_cancel"
_KEY_OUTPUT_DIR = "safety_review_output_dir"
_KEY_INSTALLING = "safety_review_installing"
_KEY_INFO = "safety_review_info"
_KEY_RUN = "safety_review_run"
_KEY_BLOCK_SIZE = "safety_review_block_size"
_KEY_PADDING = "safety_review_padding"
_KEY_TIME = "safety_review_time"
_KEY_OVERWRITE = "safety_review_overwrite"
_KEY_SCAN_ALL_DONE = "safety_review_scan_all_done"
_KEY_BATCH_DONE = "safety_review_batch_done"

_DEFAULT_BROWSE = "Browse..."
_DEFAULT_INSTALLING = "Installing dependencies..."
_DEFAULT_INFO = (
    "Detects and mosaics exposed genitalia (male & female). "
    "Nipples are NOT mosaiced."
)
_DEFAULT_TIME = "Elapsed: {elapsed}    ETA: {eta}    (~{speed:.1f}s / image)"


def _ensure_deps(parent, on_ready, mode: str = MODE_REAL, precise: bool = False):
    if mode == MODE_AUTO:
        pkgs = list(REQUIRED_PACKAGES_AUTO)
    elif mode == MODE_ANIME:
        pkgs = list(REQUIRED_PACKAGES_ANIME)
    else:
        pkgs = list(REQUIRED_PACKAGES_REAL)
    if precise:
        pkgs += [p for p in REQUIRED_PACKAGES_PRECISE if p not in pkgs]
    try:
        ensure_dependencies(parent, pkgs, on_ready)
    except Exception:
        logger.error("ensure_dependencies raised", exc_info=True)


def _fmt_time(seconds: float) -> str:
    """Format a duration in seconds as ``Hh MMm SSs`` (trimmed)."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def _selected_categories(cat_checks) -> frozenset[str]:
    return frozenset(cat for cat, cb in cat_checks.items() if cb.isChecked())


def _reload_grid_or_deepzoom(gui) -> None:
    """Refresh the tile grid or the current deep-zoom image after writes."""
    try:
        if gui.tile_grid_mode:
            gui.load_tile_grid_async(list(gui.model.images))
        elif gui.deep_zoom:
            images = gui.model.images
            if images and 0 <= gui.current_index < len(images):
                gui._clear_deep_zoom()
                gui.load_deep_zoom_image(images[gui.current_index])
    except Exception:  # noqa: BLE001 - best-effort refresh of the host viewer; logged
        logger.debug("Viewer reload failed", exc_info=True)


def _format_result_message(lang, success, failed, total_regions) -> str:
    """Build the completion summary, with or without a region count."""
    if total_regions >= 0:
        return lang.get(
            _KEY_SCAN_ALL_DONE,
            "Done — {success}/{total} images processed, "
            "{regions} region(s) mosaiced, {failed} failed.",
        ).format(
            success=success, total=success + failed,
            regions=total_regions, failed=failed,
        )
    return lang.get(
        _KEY_BATCH_DONE, "Processed {success}/{total} image(s)",
    ).format(success=success, total=success + failed)


class _WorkerHostMixin:
    """Shared worker lifecycle: progress/time rendering and clean teardown."""

    def _render_time(self, current, time_args):
        if len(time_args) < 2:
            return
        elapsed, eta = time_args[0], time_args[1]
        eta_str = _fmt_time(eta) if current > 0 else "..."
        self._time_label.setText(
            self._lang.get(_KEY_TIME, _DEFAULT_TIME).format(
                elapsed=_fmt_time(elapsed),
                eta=eta_str,
                speed=elapsed / max(current, 1),
            )
        )

    def _cleanup(self):
        self._worker = None

    def _stop_worker(self):
        # Ask the worker to stop at its next interruption check, then wait for it
        # to actually finish before dropping the reference. The old wait(5000)
        # dropped the reference on timeout while the detection thread (ONNX
        # inference) was still running, destroying a live QThread and crashing
        # the process (0xC0000409) — most visibly on Cancel-then-reuse.
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            with contextlib.suppress(RuntimeError, TypeError):
                worker.disconnect()
            worker.wait()
        self._worker = None

    def reject(self):
        # Cancel / Escape close the dialog via reject(), which does NOT deliver a
        # QCloseEvent — so without stopping the worker here it kept running and
        # was destroyed when the dialog was garbage-collected.
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):
        self._stop_worker()
        super().closeEvent(event)
