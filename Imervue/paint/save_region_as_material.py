"""Save a canvas region into the material library as a PNG.

The "make my own material" workflow MediBang exposes via the
materials panel's right-click menu: pick a region of the current
canvas (via the active selection or an explicit rect), and the
selected pixels become a fresh tile saved into the library folder.
The next time the dock rescans the library, the new tile shows up
ready to drag back onto another canvas.

Pure helper — Pillow + numpy + filesystem. Qt drag-drop and dock
refresh wiring lives in the workspace; this module is what the
verb calls to do the actual disk write.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.paint.material_library import (
    MATERIAL_CATEGORIES,
    DEFAULT_CATEGORY,
    MaterialEntry,
)


def selection_bounds(selection: np.ndarray | None) -> tuple[int, int, int, int] | None:
    """``(x, y, w, h)`` bounding rect of a True-pixel selection.

    Returns ``None`` for an empty / fully-False mask. Convenience
    so the caller doesn't have to import yet another module to do
    "selection → rect" before saving it.
    """
    if selection is None:
        return None
    if selection.dtype != np.bool_:
        raise ValueError(
            f"selection must be bool, got dtype {selection.dtype}",
        )
    if not selection.any():
        return None
    ys, xs = np.nonzero(selection)
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max())
    y1 = int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def save_region_as_material(
    canvas: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    library_root: str | Path,
    name: str,
    category: str = DEFAULT_CATEGORY,
) -> MaterialEntry:
    """Crop ``canvas`` to ``rect`` and write it under the library root.

    ``library_root`` is the on-disk material library directory; the
    new tile lands in the ``category`` subfolder (created if missing)
    so :meth:`MaterialIndex.from_directory` picks it up on the next
    rescan. ``name`` becomes the file stem; the ``.png`` extension is
    enforced so the index's filter accepts it.

    Returns the freshly-built :class:`MaterialEntry` so the caller
    can splice it into the live index without a full rescan.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got shape={canvas.shape}"
            f" dtype={canvas.dtype}",
        )
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ValueError(f"rect dimensions must be positive, got {rect!r}")
    h_canvas, w_canvas = canvas.shape[:2]
    if x < 0 or y < 0 or x + w > w_canvas or y + h > h_canvas:
        raise ValueError(
            f"rect {rect!r} falls outside canvas {(w_canvas, h_canvas)}",
        )
    if not str(name).strip():
        raise ValueError("name must be non-empty")
    if category not in MATERIAL_CATEGORIES:
        raise ValueError(
            f"unknown category {category!r}; expected one of {MATERIAL_CATEGORIES}",
        )
    safe_name = "".join(
        ch for ch in str(name)
        if ch.isalnum() or ch in (" ", "-", "_")
    ).strip()
    if not safe_name:
        raise ValueError("name has no usable filename characters")

    target_dir = Path(library_root) / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / f"{safe_name}.png").resolve()

    region = canvas[y : y + h, x : x + w]
    Image.fromarray(np.ascontiguousarray(region), mode="RGBA").save(target_path)
    return MaterialEntry(
        name=safe_name,
        path=target_path,
        category=category,
        tags=(),
    )
