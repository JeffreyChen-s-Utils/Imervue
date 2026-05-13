"""Pure-numpy deformer implementations.

Each deformer's ``apply(vertices, form)`` takes a HxWx2 vertex array
and a form dict (the schema is documented in ``FORMAT.md``) and
returns a new vertex array with the deformer's transform applied.

No Qt, no GL, no OpenGL state — these run inside the per-frame
parameter-sampling loop driven by the runtime composer. Every
operation is vectorised so a 5000-vertex puppet still hits 60 FPS on
the CPU.
"""
from __future__ import annotations

from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Rotation deformer
# ---------------------------------------------------------------------------


def apply_rotation(vertices: np.ndarray, form: dict[str, Any]) -> np.ndarray:
    """Rotate ``vertices`` (Nx2) around ``form['anchor']`` by
    ``form['angle']`` radians and return the new positions.

    Missing fields fall back to a no-op (identity) so partial forms
    coming from interpolated parameter keys don't blow up.
    """
    angle = float(form.get("angle", 0.0))
    if angle == 0.0:
        return vertices
    anchor = _xy(form.get("anchor", (0.0, 0.0)))
    return _rotate(vertices, anchor, angle)


def _rotate(vertices: np.ndarray, anchor: np.ndarray, angle: float) -> np.ndarray:
    cos_a = float(np.cos(angle))
    sin_a = float(np.sin(angle))
    rel = vertices - anchor
    out = np.empty_like(vertices)
    out[..., 0] = rel[..., 0] * cos_a - rel[..., 1] * sin_a + anchor[0]
    out[..., 1] = rel[..., 0] * sin_a + rel[..., 1] * cos_a + anchor[1]
    return out


# ---------------------------------------------------------------------------
# Skeletal LBS — multi-bone vertex blending
# ---------------------------------------------------------------------------


def apply_skeleton_lbs(
    rest_vertices: np.ndarray,
    bones: list[dict[str, Any]],
    weights_per_bone: dict[str, np.ndarray],
) -> np.ndarray:
    """Linear blend skinning. For each rest vertex, blend the rotated
    positions produced by every bone, weighted by that vertex's weight
    in each bone.

    Parameters
    ----------
    rest_vertices : (N, 2) float array — vertices in their authored
        rest position.
    bones : list of ``{"bone_id": str, "anchor": (x, y), "angle": rad}``
        — one entry per bone driving this drawable.
    weights_per_bone : dict mapping ``bone_id`` to a length-N float
        array. Missing bones get an implicit zero-weight column.

    Returns the blended (N, 2) vertex positions. A vertex whose weight
    sums to zero across all bones keeps its rest position; non-zero
    weight sums are normalised so total influence is exactly one,
    making the function tolerant of weight-list rounding errors."""
    n = len(rest_vertices)
    blended = np.zeros_like(rest_vertices)
    total = np.zeros(n, dtype=rest_vertices.dtype)
    for bone in bones:
        bone_id = bone.get("bone_id")
        if bone_id is None:
            continue
        weights = weights_per_bone.get(bone_id)
        if weights is None:
            continue
        weights_arr = np.asarray(weights, dtype=rest_vertices.dtype)
        if weights_arr.shape != (n,):
            continue
        if not np.any(weights_arr > 0):
            continue
        anchor = _xy(bone.get("anchor", (0.0, 0.0)))
        angle = float(bone.get("angle", 0.0))
        rotated = _rotate(rest_vertices, anchor, angle)
        blended += weights_arr[:, None] * rotated
        total += weights_arr
    no_influence = total <= 0.0
    if no_influence.any():
        blended[no_influence] = rest_vertices[no_influence]
        total[no_influence] = 1.0
    return blended / total[:, None]


# ---------------------------------------------------------------------------
# Warp deformer (bilinear lattice)
# ---------------------------------------------------------------------------


def apply_warp(vertices: np.ndarray, form: dict[str, Any]) -> np.ndarray:
    """Re-map ``vertices`` through a ``rows × cols`` lattice grid.

    The grid is the warp's authoring control: at neutral pose each
    cell occupies one rectangular slice of the bounds rectangle, and
    the user can drag the lattice points to bend the underlying mesh.
    Vertices inside the bounds are bilinearly interpolated from the
    four enclosing lattice points; vertices outside are passed through
    unchanged.

    Form fields:
    * ``rows``, ``cols`` — int dimensions of the lattice (≥ 2 each)
    * ``grid`` — list of rows × cols ``[x, y]`` floats; row-major
    * ``bounds`` — ``[x_min, y_min, x_max, y_max]``; the rectangle the
      grid covers in canvas-space at neutral pose
    """
    grid = form.get("grid")
    bounds = form.get("bounds")
    rows = int(form.get("rows", 0))
    cols = int(form.get("cols", 0))
    if not grid or not bounds or rows < 2 or cols < 2:
        return vertices
    bounds_arr = np.asarray(bounds, dtype=np.float64)
    if bounds_arr.shape != (4,):
        return vertices
    grid_arr = np.asarray(grid, dtype=np.float64)
    if grid_arr.shape != (rows, cols, 2):
        # Caller gave a flat row-major list; reshape.
        try:
            grid_arr = grid_arr.reshape(rows, cols, 2)
        except ValueError:
            return vertices
    return _warp_bilinear(vertices, grid_arr, bounds_arr, rows, cols)


def _warp_bilinear(
    vertices: np.ndarray,
    grid: np.ndarray,
    bounds: np.ndarray,
    rows: int,
    cols: int,
) -> np.ndarray:
    x_min, y_min, x_max, y_max = bounds
    width = max(x_max - x_min, 1e-9)
    height = max(y_max - y_min, 1e-9)
    # Normalised coords inside the bounds, clipped so out-of-bounds
    # vertices snap to the lattice edge (== unchanged motion).
    inside = (
        (vertices[..., 0] >= x_min) & (vertices[..., 0] <= x_max)
        & (vertices[..., 1] >= y_min) & (vertices[..., 1] <= y_max)
    )
    out = vertices.copy()
    if not inside.any():
        return out
    pts = vertices[inside]
    u = (pts[..., 0] - x_min) / width * (cols - 1)
    v = (pts[..., 1] - y_min) / height * (rows - 1)
    cell_x = np.clip(u.astype(np.int64), 0, cols - 2)
    cell_y = np.clip(v.astype(np.int64), 0, rows - 2)
    fx = u - cell_x
    fy = v - cell_y

    p00 = grid[cell_y, cell_x]          # top-left
    p10 = grid[cell_y, cell_x + 1]      # top-right
    p01 = grid[cell_y + 1, cell_x]      # bottom-left
    p11 = grid[cell_y + 1, cell_x + 1]  # bottom-right

    fx_col = fx[:, None]
    fy_col = fy[:, None]
    top = p00 * (1.0 - fx_col) + p10 * fx_col
    bot = p01 * (1.0 - fx_col) + p11 * fx_col
    mapped = top * (1.0 - fy_col) + bot * fy_col
    out[inside] = mapped.astype(out.dtype, copy=False)
    return out


# ---------------------------------------------------------------------------
# Default form helpers — used by the editor to seed new deformers
# ---------------------------------------------------------------------------


def default_rotation_form(anchor: tuple[float, float]) -> dict[str, Any]:
    return {"anchor": [float(anchor[0]), float(anchor[1])], "angle": 0.0}


def default_warp_form(
    bounds: tuple[float, float, float, float], rows: int = 5, cols: int = 5,
) -> dict[str, Any]:
    """Build a warp at neutral pose: lattice points evenly spaced
    across ``bounds``."""
    x_min, y_min, x_max, y_max = bounds
    grid: list[list[list[float]]] = []
    for r in range(rows):
        row = []
        for c in range(cols):
            x = x_min + (x_max - x_min) * (c / (cols - 1))
            y = y_min + (y_max - y_min) * (r / (rows - 1))
            row.append([float(x), float(y)])
        grid.append(row)
    return {
        "rows": int(rows),
        "cols": int(cols),
        "grid": grid,
        "bounds": [float(x_min), float(y_min), float(x_max), float(y_max)],
    }


# ---------------------------------------------------------------------------
# Form blending — used by parameter key interpolation
# ---------------------------------------------------------------------------


def blend_forms(a: dict[str, Any], b: dict[str, Any], t: float) -> dict[str, Any]:
    """Linearly interpolate every numeric leaf in ``a`` toward ``b``
    at parameter t in [0, 1]. Unknown / non-numeric keys keep ``a``'s
    value. Used by ``runtime.sample_parameter`` to smooth between key
    forms; runs once per (parameter × deformer) pair per frame so
    keep it lean.
    """
    if t <= 0.0:
        return dict(a)
    if t >= 1.0:
        return dict(b)
    out: dict[str, Any] = {}
    for key, va in a.items():
        vb = b.get(key)
        out[key] = _lerp_value(va, vb, t)
    # Honour b-only keys too so b can introduce a field a didn't have.
    for key, vb in b.items():
        if key not in out:
            out[key] = vb
    return out


def _lerp_value(va: Any, vb: Any, t: float) -> Any:
    if vb is None:
        return va
    if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
        return float(va) * (1.0 - t) + float(vb) * t
    if isinstance(va, list) and isinstance(vb, list) and len(va) == len(vb):
        return [_lerp_value(va[i], vb[i], t) for i in range(len(va))]
    return va


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xy(raw: Any) -> np.ndarray:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return np.asarray([float(raw[0]), float(raw[1])], dtype=np.float64)
    return np.zeros(2, dtype=np.float64)
