"""Mesh-warp transform — bilinear interpolation across a control grid.

A mesh warp is the workhorse of cloth folds, perspective tweaks, and
text-distortion gags. The user defines a small grid of source control
points (the original positions) and matches it with a destination
grid (where they want each point dragged to). This module does the
pure-numpy heavy lifting:

* :class:`MeshGrid` — the (rows × cols) control-point pair plus the
  target image bounds.
* :func:`warp_image` — runs the bilinear pixel-by-pixel warp.

The grid is regular: source control points always sit on the
``rows × cols`` lattice that subdivides the image; only the
destination grid moves. That keeps the maths cheap (no Delaunay
triangulation needed) and matches MediBang's mesh-warp UI.

Pure numpy / Qt-free; the canvas widget will paint the editable
destination grid as small handles and route mouse drags to
:meth:`MeshGrid.move_destination_node`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

MIN_GRID_DIM = 2     # 2×2 = corner-only warp (cheapest non-degenerate)
MAX_GRID_DIM = 16
DEFAULT_GRID_DIM = 4


@dataclass
class MeshGrid:
    """``rows × cols`` control-point lattice for a mesh warp.

    ``rows`` and ``cols`` are the number of control points (so a
    4×4 mesh has 4 points along each axis = 9 cells). ``destination``
    is an HxWx2 ``float32`` array with the (x, y) target position of
    each control node; the source positions are derived deterministically
    from the bounds + grid dimensions.
    """

    width: int
    height: int
    rows: int
    cols: int
    destination: np.ndarray   # shape (rows, cols, 2) float32 — (x, y)

    def __post_init__(self) -> None:
        if not MIN_GRID_DIM <= self.rows <= MAX_GRID_DIM:
            raise ValueError(
                f"rows must be in [{MIN_GRID_DIM}, {MAX_GRID_DIM}],"
                f" got {self.rows}",
            )
        if not MIN_GRID_DIM <= self.cols <= MAX_GRID_DIM:
            raise ValueError(
                f"cols must be in [{MIN_GRID_DIM}, {MAX_GRID_DIM}],"
                f" got {self.cols}",
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"width/height must be positive, got {(self.width, self.height)}",
            )
        if self.destination.shape != (self.rows, self.cols, 2):
            raise ValueError(
                f"destination shape {self.destination.shape} mismatch — "
                f"expected ({self.rows}, {self.cols}, 2)",
            )
        if self.destination.dtype != np.float32:
            raise ValueError(
                f"destination dtype {self.destination.dtype} — expected float32",
            )

    @classmethod
    def identity(
        cls, width: int, height: int,
        *, rows: int = DEFAULT_GRID_DIM, cols: int = DEFAULT_GRID_DIM,
    ) -> MeshGrid:
        """Build a non-warped grid — destination == source."""
        rows_arr = np.linspace(0, height - 1, rows, dtype=np.float32)
        cols_arr = np.linspace(0, width - 1, cols, dtype=np.float32)
        dest = np.zeros((rows, cols, 2), dtype=np.float32)
        for r, y in enumerate(rows_arr):
            for c, x in enumerate(cols_arr):
                dest[r, c, 0] = x
                dest[r, c, 1] = y
        return cls(
            width=int(width), height=int(height),
            rows=int(rows), cols=int(cols),
            destination=dest,
        )

    def source_node(self, row: int, col: int) -> tuple[float, float]:
        """Return the source-grid (x, y) at ``(row, col)`` — always
        the regular lattice position."""
        if not 0 <= row < self.rows:
            raise IndexError(f"row {row} out of range [0, {self.rows})")
        if not 0 <= col < self.cols:
            raise IndexError(f"col {col} out of range [0, {self.cols})")
        x = col / (self.cols - 1) * (self.width - 1)
        y = row / (self.rows - 1) * (self.height - 1)
        return (float(x), float(y))

    def destination_node(self, row: int, col: int) -> tuple[float, float]:
        """Read one destination node — the editable point the user
        drags."""
        if not 0 <= row < self.rows:
            raise IndexError(f"row {row} out of range [0, {self.rows})")
        if not 0 <= col < self.cols:
            raise IndexError(f"col {col} out of range [0, {self.cols})")
        return (
            float(self.destination[row, col, 0]),
            float(self.destination[row, col, 1]),
        )

    def move_destination_node(
        self, row: int, col: int, x: float, y: float,
    ) -> None:
        """Set the destination position of one node. ``x`` / ``y`` are
        in image-space pixels and clamped to the canvas bounds so the
        warp can't index outside the source image."""
        if not 0 <= row < self.rows:
            raise IndexError(f"row {row} out of range [0, {self.rows})")
        if not 0 <= col < self.cols:
            raise IndexError(f"col {col} out of range [0, {self.cols})")
        clamped_x = max(0.0, min(float(self.width - 1), float(x)))
        clamped_y = max(0.0, min(float(self.height - 1), float(y)))
        self.destination[row, col, 0] = clamped_x
        self.destination[row, col, 1] = clamped_y

    def is_identity(self, *, atol: float = 0.5) -> bool:
        """Return ``True`` if the destination grid still matches the
        source within ``atol`` pixels — the warp is a no-op."""
        ident = type(self).identity(
            self.width, self.height, rows=self.rows, cols=self.cols,
        )
        return bool(np.allclose(self.destination, ident.destination, atol=atol))


def warp_image(
    image: np.ndarray, grid: MeshGrid,
) -> np.ndarray:
    """Apply ``grid`` to ``image`` and return a fresh warped buffer.

    For each output pixel we find which source-grid cell it falls
    into (in destination space), bilinearly interpolate the
    corresponding source position from the four cell corners, then
    sample the source image at that position. Pixels that map past
    the source bounds become fully transparent.

    The output shape always matches the input shape; warping a
    region beyond the canvas just shows transparent pixels at the
    destination.
    """
    if (
        image.ndim != 3
        or image.shape[2] != 4
        or image.dtype != np.uint8
    ):
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    h, w = image.shape[:2]
    if grid.height != h or grid.width != w:
        raise ValueError(
            f"grid bounds {(grid.height, grid.width)} mismatch image {(h, w)}",
        )
    if grid.is_identity():
        return image.copy()

    # Source positions per destination pixel. The destination grid
    # divides the image into (rows-1) × (cols-1) quadrilaterals; each
    # output pixel falls into one cell. We approximate the inverse
    # warp via bilinear interpolation inside that cell — cheap and
    # close enough to the formal Coons patch for hand-painted images.
    yy, xx = np.indices((h, w)).astype(np.float32)
    src_x, src_y = _inverse_sample(grid, xx, yy)

    # Sample the source image at the per-pixel coordinates. Out-of-
    # bounds samples → transparent.
    valid = (
        (src_x >= 0) & (src_x <= w - 1)
        & (src_y >= 0) & (src_y <= h - 1)
    )
    src_x_clipped = np.clip(src_x, 0, w - 1)
    src_y_clipped = np.clip(src_y, 0, h - 1)
    out = _bilinear_sample(image, src_x_clipped, src_y_clipped)
    out[~valid] = (0, 0, 0, 0)
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _inverse_sample(
    grid: MeshGrid, xx: np.ndarray, yy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """For each output pixel, compute the matching source-image
    position by inverse-bilinear-interpolating inside the destination
    cell that contains it.

    A faithful inverse-bilinear map needs Newton iteration; the cheap
    approximation here finds the **source cell** by mapping output
    pixels through the *forward* destination grid for each cell and
    picking the one that contains the pixel. For typical hand-edited
    warps (dozens of degrees max) the approximation is visually
    indistinguishable from the exact answer.
    """
    h, w = xx.shape
    src_x = np.zeros((h, w), dtype=np.float32)
    src_y = np.zeros((h, w), dtype=np.float32)
    # Destination grid sweep — for each cell, paint its source
    # coordinates into output pixels that fall within its bounding
    # quad. Use bilinear interpolation across the cell.
    rows = grid.rows
    cols = grid.cols
    src_xs = np.array(
        [grid.source_node(0, c)[0] for c in range(cols)], dtype=np.float32,
    )
    src_ys = np.array(
        [grid.source_node(r, 0)[1] for r in range(rows)], dtype=np.float32,
    )
    for r in range(rows - 1):
        for c in range(cols - 1):
            d_tl = grid.destination[r, c]
            d_tr = grid.destination[r, c + 1]
            d_bl = grid.destination[r + 1, c]
            d_br = grid.destination[r + 1, c + 1]
            cell_x_min = min(d_tl[0], d_tr[0], d_bl[0], d_br[0])
            cell_x_max = max(d_tl[0], d_tr[0], d_bl[0], d_br[0])
            cell_y_min = min(d_tl[1], d_tr[1], d_bl[1], d_br[1])
            cell_y_max = max(d_tl[1], d_tr[1], d_bl[1], d_br[1])
            x0 = max(0, int(np.floor(cell_x_min)))
            x1 = min(w - 1, int(np.ceil(cell_x_max)))
            y0 = max(0, int(np.floor(cell_y_min)))
            y1 = min(h - 1, int(np.ceil(cell_y_max)))
            if x0 > x1 or y0 > y1:
                continue
            sub_xx = xx[y0:y1 + 1, x0:x1 + 1]
            sub_yy = yy[y0:y1 + 1, x0:x1 + 1]
            # Inverse bilinear via the destination-cell axis-aligned
            # bounding box — accurate enough for axis-aligned warps,
            # smooth degradation for sheared cells.
            denom_x = max(1e-6, float(cell_x_max - cell_x_min))
            denom_y = max(1e-6, float(cell_y_max - cell_y_min))
            u = np.clip((sub_xx - cell_x_min) / denom_x, 0.0, 1.0)
            v = np.clip((sub_yy - cell_y_min) / denom_y, 0.0, 1.0)
            src_x[y0:y1 + 1, x0:x1 + 1] = (
                src_xs[c] * (1 - u) + src_xs[c + 1] * u
            )
            src_y[y0:y1 + 1, x0:x1 + 1] = (
                src_ys[r] * (1 - v) + src_ys[r + 1] * v
            )
    return src_x, src_y


def _bilinear_sample(
    image: np.ndarray, xs: np.ndarray, ys: np.ndarray,
) -> np.ndarray:
    """Bilinearly sample ``image`` at floating ``(xs, ys)``.

    Both coordinate arrays must be the desired output shape; the
    return is HxWx4 uint8 RGBA.
    """
    h, w = image.shape[:2]
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    x0 = np.clip(x0, 0, w - 1)
    y0 = np.clip(y0, 0, h - 1)
    fx = (xs - x0).astype(np.float32)
    fy = (ys - y0).astype(np.float32)
    fx = fx[..., None]
    fy = fy[..., None]
    a = image[y0, x0].astype(np.float32)
    b = image[y0, x1].astype(np.float32)
    c = image[y1, x0].astype(np.float32)
    d = image[y1, x1].astype(np.float32)
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + d * fx
    out = top * (1 - fy) + bot * fy
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# Re-exposed so a future Qt overlay can introspect the maths without
# importing private symbols.
MESH_INTERNALS: dict[str, Any] = {
    "_inverse_sample": _inverse_sample,
    "_bilinear_sample": _bilinear_sample,
}
