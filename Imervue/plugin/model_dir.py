"""Shared helper for plugin model directories.

Plugins that ship optional ONNX / weight files keep them under
``plugins/<name>/models/``. Historically each plugin guarded against
the missing-directory case by silently returning an empty list, but
that left the directory absent on disk — so a user who wanted to drop
in their own model had to know to create the folder first.

This helper centralises two contracts:

* :func:`ensure_model_dir` creates the directory if it does not exist
  (idempotent, safe across concurrent plugin loads), and returns the
  resolved :class:`Path` so callers can chain.
* :func:`discover_models` couples ``ensure_model_dir`` with a glob,
  so the typical "list every ``*.onnx`` in this folder" call site
  reduces to one line and never fails when the folder is missing.

The helper deliberately does no I/O beyond ``mkdir`` and ``glob`` —
it must be safe to call at module-import time of a plugin.
"""
from __future__ import annotations

from pathlib import Path


def ensure_model_dir(path: str | Path) -> Path:
    """Create ``path`` if it does not exist; return the resolved Path.

    ``parents=True`` so a never-installed plugin folder also gets the
    intermediate ``models/`` parent. ``exist_ok=True`` keeps the call
    idempotent — concurrent plugin loads (the manager imports plugins
    in parallel during startup) will not race each other.
    """
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def discover_models(
    path: str | Path, pattern: str = "*.onnx",
) -> list[Path]:
    """Return every file under ``path`` matching ``pattern``.

    The directory is created on first call, so callers never have to
    pre-check ``Path.is_dir()`` and the user can always find the
    folder in their file manager when they want to drop in weights.
    Returns an empty list when the directory exists but contains no
    matching files — same shape as the previous per-plugin helper.
    """
    return list(ensure_model_dir(path).glob(pattern))
