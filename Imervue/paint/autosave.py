"""Auto-save crash-recovery snapshots.

Every ``DEFAULT_INTERVAL_SEC`` seconds the workspace asks
:func:`take_snapshot` to write the current canvas composite to disk
under ``<app_dir>/autosave/``. On the next launch the workspace
calls :func:`latest_snapshot` to surface the most recent file as a
"restore previous session?" prompt.

Snapshots are PNG (lossless RGBA) named with a sortable timestamp
so :func:`latest_snapshot` can pick "most recent" by name alone
without a separate index file. Old snapshots beyond the documented
retention cap are pruned by :func:`prune_snapshots` so the autosave
folder doesn't grow without bound.

Pure-numpy / Pillow / Qt-free so the lifecycle can be exercised in
unit tests without a display server.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.system.app_paths import app_dir

AUTOSAVE_DIR_NAME = "autosave"
AUTOSAVE_PREFIX = "autosave_"
AUTOSAVE_SUFFIX = ".png"
DEFAULT_INTERVAL_SEC = 120
MAX_RETAINED_SNAPSHOTS = 10

_TIMESTAMP_RE = re.compile(
    r"^autosave_(\d{8}_\d{6}_\d{6})\.png$",
)


def autosave_dir() -> Path:
    """Return the directory autosaves live in (created on demand)."""
    target = app_dir() / AUTOSAVE_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def take_snapshot(
    composite: np.ndarray,
    *,
    target_dir: Path | None = None,
    now: float | None = None,
) -> Path:
    """Write ``composite`` to a fresh timestamped PNG and return its path.

    ``now`` is injected for test determinism; production code lets
    it default to ``time.time()``. Pruning runs after the new file
    lands so the count cap is enforced even if the caller forgets
    to drive :func:`prune_snapshots` separately.
    """
    if (
        composite.ndim != 3
        or composite.shape[2] != 4
        or composite.dtype != np.uint8
    ):
        raise ValueError(
            f"composite must be HxWx4 uint8 RGBA, got {composite.shape}"
            f" {composite.dtype}",
        )
    folder = (target_dir or autosave_dir())
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _format_timestamp(now if now is not None else time.time())
    path = folder / f"{AUTOSAVE_PREFIX}{stamp}{AUTOSAVE_SUFFIX}"
    Image.fromarray(composite, mode="RGBA").save(path)
    prune_snapshots(target_dir=folder)
    return path.resolve()


def list_snapshots(*, target_dir: Path | None = None) -> list[Path]:
    """Return autosave files sorted oldest → newest by filename."""
    folder = (target_dir or autosave_dir())
    if not folder.is_dir():
        return []
    files = [
        p for p in folder.iterdir()
        if p.is_file() and _TIMESTAMP_RE.match(p.name)
    ]
    files.sort(key=lambda p: p.name)
    return files


def latest_snapshot(*, target_dir: Path | None = None) -> Path | None:
    """Return the most recent snapshot, or ``None`` if none exists."""
    files = list_snapshots(target_dir=target_dir)
    return files[-1] if files else None


def load_snapshot(path: Path) -> np.ndarray:
    """Decode a snapshot PNG into an HxWx4 uint8 RGBA buffer."""
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        return np.ascontiguousarray(np.array(rgba, dtype=np.uint8))


def prune_snapshots(
    *, target_dir: Path | None = None, keep: int = MAX_RETAINED_SNAPSHOTS,
) -> int:
    """Drop the oldest snapshots once the count exceeds ``keep``.

    Returns how many files were deleted. Failure to delete a single
    file (locked by a viewer, permissions) is swallowed silently;
    the next prune pass picks it back up.
    """
    keep = max(keep, 1)
    files = list_snapshots(target_dir=target_dir)
    excess = max(0, len(files) - keep)
    if excess == 0:
        return 0
    deleted = 0
    for p in files[:excess]:
        try:
            p.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted


def clear_snapshots(*, target_dir: Path | None = None) -> int:
    """Wipe every snapshot — used after a successful explicit save."""
    files = list_snapshots(target_dir=target_dir)
    deleted = 0
    for p in files:
        try:
            p.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted


def _format_timestamp(seconds: float) -> str:
    """Stable, sortable timestamp derived from ``time.time()`` seconds.

    Includes microseconds so two snapshots taken in the same second
    don't collide. ``YYYYMMDD_HHMMSS_microseconds`` keeps the
    string-sort order equal to chronological order.
    """
    seconds = float(seconds)
    whole = int(seconds)
    micros = int(round((seconds - whole) * 1_000_000)) % 1_000_000
    lt = time.localtime(whole)
    return (
        f"{lt.tm_year:04d}{lt.tm_mon:02d}{lt.tm_mday:02d}_"
        f"{lt.tm_hour:02d}{lt.tm_min:02d}{lt.tm_sec:02d}_"
        f"{micros:06d}"
    )
