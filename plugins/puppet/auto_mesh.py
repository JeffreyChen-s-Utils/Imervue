"""Auto-mesh generation from a PNG → ``PuppetDocument``.

The Phase-3 onboarding path: drag a PNG into the workspace, get back a
single-drawable puppet whose mesh is a triangulated grid that respects
the image's alpha. Keeps the user from having to author meshes by hand
before they can see Phase 4's deformer sliders move pixels.

Pure-Python (numpy + Pillow); the workspace does the file I/O and
turns the result into a saved ``.puppet``.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np

from puppet.document import Drawable, PuppetDocument

DEFAULT_CELL_SIZE: int = 64
"""Image-pixel side length of one grid cell. Smaller = denser mesh +
finer deformations + slower per-frame transform pass."""

_ALPHA_THRESHOLD: int = 1
"""A cell whose alpha max is below this threshold is considered fully
transparent and dropped from the mesh — keeps offscreen empty space
out of the triangulation."""


def triangulate_alpha_grid(
    image_rgba: np.ndarray, cell_size: int = DEFAULT_CELL_SIZE,
) -> tuple[list[tuple[float, float]], list[int], list[tuple[float, float]]]:
    """Triangulate ``image_rgba`` into a grid of cells with cell side
    ``cell_size``, dropping cells whose alpha is fully zero.

    Returns ``(vertices, indices, uvs)``:
    * ``vertices`` — list of ``(x, y)`` floats in image-space pixels
    * ``indices`` — flat list of triangle indices (length divisible by 3)
    * ``uvs`` — list of ``(u, v)`` floats in ``[0, 1]`` matching ``vertices``

    Vertex deduplication is by integer grid coordinate so adjacent
    cells share corners (cuts the vertex count roughly in half versus
    naïvely emitting six vertices per cell).

    Raises :class:`ValueError` for empty inputs or if no cell survives
    the alpha threshold (an entirely-transparent image is not a useful
    puppet).
    """
    if image_rgba.ndim != 3 or image_rgba.shape[2] != 4:
        raise ValueError(
            f"image must be HxWx4 RGBA, got shape {image_rgba.shape}",
        )
    if cell_size <= 0:
        raise ValueError(f"cell_size must be > 0, got {cell_size}")

    h, w = image_rgba.shape[:2]
    if h == 0 or w == 0:
        raise ValueError("image is empty")

    alpha = image_rgba[..., 3]
    cells_y = max(1, (h + cell_size - 1) // cell_size)
    cells_x = max(1, (w + cell_size - 1) // cell_size)

    vertex_index: dict[tuple[int, int], int] = {}
    vertices: list[tuple[float, float]] = []
    uvs: list[tuple[float, float]] = []
    indices: list[int] = []

    def _vertex(gx: int, gy: int) -> int:
        key = (gx, gy)
        cached = vertex_index.get(key)
        if cached is not None:
            return cached
        idx = len(vertices)
        vertex_index[key] = idx
        x_px = min(gx * cell_size, w)
        y_px = min(gy * cell_size, h)
        vertices.append((float(x_px), float(y_px)))
        uvs.append((x_px / w, y_px / h))
        return idx

    for cy in range(cells_y):
        for cx in range(cells_x):
            x0 = cx * cell_size
            y0 = cy * cell_size
            x1 = min(x0 + cell_size, w)
            y1 = min(y0 + cell_size, h)
            cell_alpha = alpha[y0:y1, x0:x1]
            if not cell_alpha.size:
                continue
            if int(cell_alpha.max()) < _ALPHA_THRESHOLD:
                continue
            tl = _vertex(cx, cy)
            tr = _vertex(cx + 1, cy)
            br = _vertex(cx + 1, cy + 1)
            bl = _vertex(cx, cy + 1)
            indices.extend([tl, tr, br, tl, br, bl])

    if not indices:
        raise ValueError("image has no opaque pixels — nothing to triangulate")
    return vertices, indices, uvs


def puppet_from_png(
    source: str | Path | bytes,
    *,
    drawable_id: str = "main",
    texture_path: str = "textures/main.png",
    cell_size: int = DEFAULT_CELL_SIZE,
) -> PuppetDocument:
    """Build a single-drawable :class:`PuppetDocument` around ``source``.

    ``source`` is either a filesystem path or the raw PNG bytes. The
    resulting document carries one drawable named ``drawable_id`` whose
    mesh is the alpha-bounded grid triangulation, and one texture
    entry under ``texture_path``.
    """
    png_bytes = _load_png_bytes(source)
    rgba = _decode_rgba(png_bytes)
    h, w = rgba.shape[:2]
    vertices, indices, uvs = triangulate_alpha_grid(rgba, cell_size=cell_size)

    doc = PuppetDocument(size=(w, h))
    doc.textures[texture_path] = png_bytes
    doc.drawables = [
        Drawable(
            id=drawable_id,
            texture=texture_path,
            vertices=vertices,
            indices=indices,
            uvs=uvs,
            draw_order=0,
        ),
    ]
    return doc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_png_bytes(source: str | Path | bytes) -> bytes:
    if isinstance(source, bytes):
        return source
    return Path(source).read_bytes()


def _decode_rgba(png_bytes: bytes) -> np.ndarray:
    from PIL import Image
    with Image.open(io.BytesIO(png_bytes)) as img:
        return np.array(img.convert("RGBA"), dtype=np.uint8)
