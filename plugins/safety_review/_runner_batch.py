"""Per-image batch bookkeeping for the frozen-build ``_runner.py``.

Where each censored image is written, the shape retry/downgrade that keeps a
transient failure out of the failed folder, and the failed folder itself (a
mirrored copy of each failed original plus ``censor_failed.log``). Loaded as a
sibling file by the external Python, like ``_censor_core``; keep it free of
Qt, Imervue and third-party imports.
"""
from __future__ import annotations

import os
from pathlib import Path

if __package__:   # imported as part of the plugin package (tests)
    from safety_review._censor_core import _ensure_parent
    from safety_review._constants import SHAPE_ELLIPSE
else:             # run as a script next to its siblings
    from _censor_core import _ensure_parent
    from _constants import SHAPE_ELLIPSE


def _batch_destination(src, output_dir, overwrite, source_root):
    """Resolve one batch destination, mirroring subfolders under *source_root*
    when given so a recursive scan keeps its tree instead of flattening.

    Only computes the path; the directory is created on demand at write time
    so a skipped (clean) image leaves no empty output folder behind.
    """
    if overwrite:
        return src
    target_dir = output_dir
    if source_root:
        rel = os.path.relpath(os.path.dirname(src), source_root)
        if rel != os.curdir and not rel.startswith(os.pardir):
            target_dir = os.path.join(output_dir, rel)
    stem = Path(src).stem
    suffix = Path(src).suffix or ".png"
    dst = os.path.join(target_dir, f"{stem}_censored{suffix}")
    counter = 1
    while os.path.exists(dst):
        dst = os.path.join(target_dir, f"{stem}_censored_{counter}{suffix}")
        counter += 1
    return dst


def _failed_dest(src, failed_dir, scan_root):
    """Mirrored path for a failed image under *failed_dir*, keeping its name."""
    target_dir = failed_dir
    if scan_root:
        rel = os.path.relpath(os.path.dirname(src), scan_root)
        if rel != os.curdir and not rel.startswith(os.pardir):
            target_dir = os.path.join(failed_dir, rel)
    return os.path.join(target_dir, os.path.basename(src))


def _copy_failed(src, failed_dir, scan_root):
    """Best-effort copy of a failed original into the mirrored failed folder."""
    import shutil
    try:
        dst = _failed_dest(src, failed_dir, scan_root)
        _ensure_parent(dst)
        shutil.copy2(src, dst)
    except OSError:
        pass


def _process_one_with_fallback(run_for_shape, shape, retries=1):
    """Run *run_for_shape(shape)*, retrying then downgrading to ellipse before
    surfacing the error, so only a genuinely unprocessable image fails."""
    attempts = [shape] * (1 + max(0, retries))
    if shape != SHAPE_ELLIPSE:
        attempts.append(SHAPE_ELLIPSE)
    last_exc = None
    for attempt_shape in attempts:
        try:
            return run_for_shape(attempt_shape)
        except Exception as exc:  # noqa: BLE001 - detector/torch fail in any way; re-raised below
            last_exc = exc
    raise last_exc


def _write_failed_log(failed_dir, failures):
    if failures and failed_dir:
        with open(os.path.join(failed_dir, "censor_failed.log"),
                  "w", encoding="utf-8") as fh:
            for fname, reason in failures:
                fh.write(f"{fname}: {reason}\n")
