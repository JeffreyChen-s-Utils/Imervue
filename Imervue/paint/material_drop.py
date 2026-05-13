"""Drop-a-material-onto-canvas helper.

raster paint apps lets the artist drag a tile out of the materials dock onto
the canvas; the drop creates a new raster layer with the material
pasted in at the drop position. This module is the pure-numpy logic
that performs the paste plus the constants the Qt drag-source and
drop-target need to agree on (the MIME type identifying a material).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Custom MIME type used by :class:`MaterialDock` to carry a material
# entry's path through Qt's drag-and-drop pipeline. The string is
# scoped to imervue so other apps' drops never accidentally interpret
# a foreign drop as a material.
MATERIAL_MIME_TYPE = "application/x-imervue-material-path"


def load_material_image(path: str | Path) -> np.ndarray:
    """Read a material file off disk into a fresh HxWx4 uint8 RGBA buffer.

    Pillow handles JPEG / PNG / BMP / TIFF transparently; the result
    is converted to RGBA so the rest of the paint pipeline can blend
    it consistently. Pure helper so callers other than the materials
    dock (export presets, recipe pipeline) can reuse it.
    """
    from PIL import Image

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"material file does not exist: {target}")
    with Image.open(target) as img:
        arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    return np.ascontiguousarray(arr)


def paste_material_at(
    canvas_shape: tuple[int, int],
    tile: np.ndarray,
    *,
    drop_x: int,
    drop_y: int,
) -> np.ndarray:
    """Build a fresh canvas-sized RGBA buffer with ``tile`` pasted at the drop.

    ``canvas_shape`` is ``(height, width)``; the result matches it.
    The drop point places the *centre* of the tile at ``(drop_x,
    drop_y)`` so the user perceives the gesture as "drop here" rather
    than "drop's top-left corner here". Tiles that overhang the
    canvas are clipped — never wrapped, never resized.
    """
    if (
        tile.ndim != 3
        or tile.shape[2] != 4
        or tile.dtype != np.uint8
    ):
        raise ValueError(
            f"tile must be HxWx4 uint8 RGBA, got shape={tile.shape}"
            f" dtype={tile.dtype}",
        )
    h_canvas, w_canvas = canvas_shape
    if h_canvas <= 0 or w_canvas <= 0:
        raise ValueError(
            f"canvas shape must be positive, got {canvas_shape!r}",
        )
    h_tile, w_tile = tile.shape[:2]
    out = np.zeros((h_canvas, w_canvas, 4), dtype=np.uint8)

    # Compute the destination rectangle on the canvas.
    dst_x0 = int(drop_x) - w_tile // 2
    dst_y0 = int(drop_y) - h_tile // 2
    dst_x1 = dst_x0 + w_tile
    dst_y1 = dst_y0 + h_tile

    # Clip against canvas bounds — produce the source rectangle in
    # the tile that survives the clip.
    src_x0 = max(0, -dst_x0)
    src_y0 = max(0, -dst_y0)
    src_x1 = w_tile - max(0, dst_x1 - w_canvas)
    src_y1 = h_tile - max(0, dst_y1 - h_canvas)

    cdst_x0 = max(0, dst_x0)
    cdst_y0 = max(0, dst_y0)
    cdst_x1 = min(w_canvas, dst_x1)
    cdst_y1 = min(h_canvas, dst_y1)

    if cdst_x0 >= cdst_x1 or cdst_y0 >= cdst_y1:
        # Drop fell entirely outside the canvas — return the empty
        # canvas-sized buffer rather than raising; the caller still
        # gets a valid layer it can attach.
        return out

    out[cdst_y0:cdst_y1, cdst_x0:cdst_x1] = tile[src_y0:src_y1, src_x0:src_x1]
    return out


def commit_material_to_document(
    document,
    tile: np.ndarray,
    *,
    drop_x: int,
    drop_y: int,
    name: str = "Material",
):
    """Append a new raster layer to ``document`` carrying the tile.

    Returns the freshly-added :class:`Imervue.paint.document.Layer`,
    or ``None`` if the document is empty (no shape) — the caller
    should never invite this case but a guard prevents a crash if
    drag-drop fires on a brand-new workspace.
    """
    shape = document.shape
    if shape is None:
        return None
    image = paste_material_at(shape, tile, drop_x=drop_x, drop_y=drop_y)
    layer = document.add_layer(name=name)
    np.copyto(layer.image, image)
    document.invalidate_composite()
    return layer
