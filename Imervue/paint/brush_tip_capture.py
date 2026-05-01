"""Capture a custom brush tip from the current selection.

Phase 25e adds the "Capture Brush Tip from Selection" verb. The user
lassoes a region of the active layer, runs the verb, and the
selected pixels are saved as a PNG under ``<app_dir>/user_brush_tips/``
where the existing brush engine + material panel pick it up.

Pure-numpy / Qt-free apart from the file-system writes; the helper
returns enough information for the workspace to register the new
tip in the material library without re-opening the saved file.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.system.app_paths import app_dir

USER_BRUSH_TIP_DIR_NAME = "user_brush_tips"
DEFAULT_TIP_NAME_PREFIX = "tip"
MIN_TIP_DIM = 4
MAX_TIP_DIM = 1024


def user_brush_tips_dir() -> Path:
    """Return the directory where captured tips live (created on demand)."""
    target = app_dir() / USER_BRUSH_TIP_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def capture_brush_tip(
    layer_image: np.ndarray, selection: np.ndarray,
) -> np.ndarray:
    """Crop the selected pixels into a tight HxWx4 RGBA brush tip.

    The selection is treated as a mask: pixels inside the bounding
    box but outside the selection have their alpha forced to 0. The
    output is the smallest rectangle that contains every selected
    pixel — this keeps brush kernels compact, matching the
    convention of every brush tip already in the library.

    Returns a fresh contiguous ``uint8`` array. Raises ``ValueError``
    on malformed inputs or empty selections so the caller can show
    a user-visible error rather than silently producing a blank tip.
    """
    if (
        layer_image.ndim != 3
        or layer_image.shape[2] != 4
        or layer_image.dtype != np.uint8
    ):
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, got {layer_image.shape}"
            f" {layer_image.dtype}",
        )
    if selection.ndim != 2 or selection.dtype != np.bool_:
        raise ValueError(
            f"selection must be HxW bool, got {selection.shape}"
            f" {selection.dtype}",
        )
    if selection.shape != layer_image.shape[:2]:
        raise ValueError(
            f"selection shape {selection.shape} does not match layer"
            f" {layer_image.shape[:2]}",
        )
    if not selection.any():
        raise ValueError("selection is empty — nothing to capture")
    ys, xs = np.where(selection)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    bbox_h = y1 - y0
    bbox_w = x1 - x0
    if bbox_h < MIN_TIP_DIM or bbox_w < MIN_TIP_DIM:
        # Pad up to the documented minimum so a tiny single-pixel
        # selection still produces a usable kernel.
        pad_h = max(0, MIN_TIP_DIM - bbox_h)
        pad_w = max(0, MIN_TIP_DIM - bbox_w)
        h_canvas, w_canvas = layer_image.shape[:2]
        y0 = max(0, y0 - pad_h // 2)
        x0 = max(0, x0 - pad_w // 2)
        y1 = min(h_canvas, y1 + (pad_h - pad_h // 2))
        x1 = min(w_canvas, x1 + (pad_w - pad_w // 2))
    if (y1 - y0) > MAX_TIP_DIM or (x1 - x0) > MAX_TIP_DIM:
        raise ValueError(
            f"selection bbox {(y1 - y0)}x{(x1 - x0)} exceeds the "
            f"{MAX_TIP_DIM}-pixel cap; crop a smaller region",
        )
    tip = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    sub_layer = layer_image[y0:y1, x0:x1]
    sub_sel = selection[y0:y1, x0:x1]
    tip[sub_sel] = sub_layer[sub_sel]
    # Pixels outside the selection inside the bbox stay (0, 0, 0, 0).
    return np.ascontiguousarray(tip)


def save_brush_tip(
    tip: np.ndarray, name: str, *, target_dir: Path | None = None,
) -> Path:
    """Save ``tip`` as a PNG and return the absolute path written.

    ``name`` is sanitised — only ascii letters / digits / underscore /
    dash survive; everything else collapses to ``_``. A duplicate
    name gets a numeric suffix appended so the user never overwrites
    a previous capture by accident.
    """
    if (
        tip.ndim != 3
        or tip.shape[2] != 4
        or tip.dtype != np.uint8
    ):
        raise ValueError(
            f"tip must be HxWx4 uint8 RGBA, got {tip.shape} {tip.dtype}",
        )
    safe = _sanitise_name(name)
    folder = (target_dir or user_brush_tips_dir())
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{safe}.png"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{safe}_{counter}.png"
        counter += 1
    Image.fromarray(tip, mode="RGBA").save(candidate)
    return candidate.resolve()


def _sanitise_name(raw: str) -> str:
    """Reduce ``raw`` to a filesystem-safe stem.

    Empty / whitespace-only names fall back to the documented prefix
    so the saved filename is always non-empty.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(raw or ""))
    cleaned = cleaned.strip("_")
    return cleaned or DEFAULT_TIP_NAME_PREFIX
