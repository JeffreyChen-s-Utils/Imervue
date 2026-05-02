"""Free-transform warps — 4-corner perspective and distort.

Mesh-warp (:mod:`Imervue.paint.mesh_warp`) covers the smooth-region
case but the user often wants the cheaper 4-handle transform that
matches Photoshop's "Perspective" and "Distort" modes:

* **Perspective** — the four corners define a projective transform,
  so straight lines in the source stay straight in the output. Used
  for keystone correction or planting a flat plate onto a tilted
  surface.
* **Distort** — the four corners define a non-projective bilinear
  warp; straight lines through the interior may curve. The model
  is "treat the output quad as a bilinear patch parameterised by
  (u, v) in [0,1]² — sample source at (u, v)·source_size".

Both modes share the same inverse-sampling pattern as mesh_warp:
walk every output pixel, compute its source coordinates, and bilinear-
sample the input. Pixels outside the quad / outside the source receive
zero alpha so the warped layer composites cleanly.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.mesh_warp import _bilinear_sample

# A degenerate quad (collinear or zero-area) makes the 8x8 system
# singular. The solver checks the rank-1 fallback instead of raising
# numpy LinAlgError so the caller can react gracefully (e.g. ignore
# the partial drag).
_RANK_EPSILON = 1e-9


def homography_from_corners(
    src_corners: np.ndarray | tuple,
    dst_corners: np.ndarray | tuple,
) -> np.ndarray | None:
    """Solve the 3×3 projective transform ``H`` mapping src → dst.

    Each corner array is shape ``(4, 2)`` ordered TL, TR, BR, BL.
    Returns the 3×3 ``float64`` matrix or ``None`` when the system
    is degenerate (collinear corners, zero-area quad).
    """
    src = np.asarray(src_corners, dtype=np.float64).reshape(4, 2)
    dst = np.asarray(dst_corners, dtype=np.float64).reshape(4, 2)
    if src.shape != (4, 2) or dst.shape != (4, 2):
        raise ValueError(
            "src and dst corners must each be shape (4, 2)",
        )
    a_rows: list[list[float]] = []
    b_rows: list[float] = []
    for (sx, sy), (dx, dy) in zip(src, dst, strict=True):
        a_rows.append([sx, sy, 1.0, 0.0, 0.0, 0.0, -sx * dx, -sy * dx])
        b_rows.append(dx)
        a_rows.append([0.0, 0.0, 0.0, sx, sy, 1.0, -sx * dy, -sy * dy])
        b_rows.append(dy)
    a = np.asarray(a_rows, dtype=np.float64)
    b = np.asarray(b_rows, dtype=np.float64)
    try:
        params, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(params)):
        return None
    h = np.array([
        [params[0], params[1], params[2]],
        [params[3], params[4], params[5]],
        [params[6], params[7], 1.0],
    ], dtype=np.float64)
    if abs(np.linalg.det(h)) < _RANK_EPSILON:
        return None
    return h


def apply_perspective_warp(
    image: np.ndarray,
    dst_corners: np.ndarray | tuple,
    *,
    output_shape: tuple[int, int],
) -> np.ndarray:
    """Warp ``image`` so its corners land at ``dst_corners``.

    ``dst_corners`` is shape ``(4, 2)`` in output-pixel space, ordered
    TL, TR, BR, BL. ``output_shape`` is ``(height, width)`` of the
    canvas we are painting into. Returns a fresh HxWx4 uint8 RGBA
    buffer; pixels outside the warped quad — or where the inverse
    map lands outside the source image — receive zero alpha.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got shape={image.shape}"
            f" dtype={image.dtype}",
        )
    h_out, w_out = output_shape
    if h_out <= 0 or w_out <= 0:
        raise ValueError(
            f"output_shape must be positive, got {output_shape!r}",
        )
    h_src, w_src = image.shape[:2]
    src_corners = np.asarray([
        [0.0, 0.0],
        [w_src - 1.0, 0.0],
        [w_src - 1.0, h_src - 1.0],
        [0.0, h_src - 1.0],
    ], dtype=np.float64)
    h_matrix = homography_from_corners(src_corners, dst_corners)
    if h_matrix is None:
        return np.zeros((h_out, w_out, 4), dtype=np.uint8)
    inv = np.linalg.inv(h_matrix)
    yy, xx = np.indices((h_out, w_out)).astype(np.float64)
    flat_x = xx.flatten()
    flat_y = yy.flatten()
    ones = np.ones_like(flat_x)
    coords = np.stack([flat_x, flat_y, ones], axis=0)
    mapped = inv @ coords
    w_component = mapped[2]
    valid = np.abs(w_component) > _RANK_EPSILON
    src_x = np.zeros_like(flat_x)
    src_y = np.zeros_like(flat_y)
    src_x[valid] = mapped[0, valid] / w_component[valid]
    src_y[valid] = mapped[1, valid] / w_component[valid]
    in_bounds = valid & (src_x >= 0) & (src_x <= w_src - 1) & (src_y >= 0) & (src_y <= h_src - 1)
    out = np.zeros((h_out, w_out, 4), dtype=np.uint8)
    if not in_bounds.any():
        return out
    flat_out = out.reshape(-1, 4)
    sample_x = src_x[in_bounds].reshape(-1)
    sample_y = src_y[in_bounds].reshape(-1)
    sampled = _bilinear_sample(image, sample_x, sample_y)
    flat_out[in_bounds] = sampled.reshape(-1, 4)
    return out


def apply_distort_warp(
    image: np.ndarray,
    dst_corners: np.ndarray | tuple,
    *,
    output_shape: tuple[int, int],
    samples_per_axis: int = 64,
) -> np.ndarray:
    """Warp ``image`` onto a bilinear quad — non-projective free distort.

    The output quad is parameterised by ``(u, v) ∈ [0,1]²``; at each
    output pixel we estimate ``(u, v)`` from the dst corners and
    sample the source at ``(u·(w_src-1), v·(h_src-1))``. Pixels that
    fall outside the dst quad receive zero alpha.

    The (u, v) estimation walks a uniform grid of
    ``samples_per_axis × samples_per_axis`` parameter samples and
    rasterises each into the output buffer; this avoids solving the
    inverse bilinear (which has a quadratic edge case). Resolution
    is fine enough that gaps between rasterised samples are smaller
    than a pixel for any quad up to ~1024² output.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got shape={image.shape}"
            f" dtype={image.dtype}",
        )
    if samples_per_axis < 2:
        raise ValueError(
            f"samples_per_axis must be >= 2, got {samples_per_axis}",
        )
    h_out, w_out = output_shape
    if h_out <= 0 or w_out <= 0:
        raise ValueError(
            f"output_shape must be positive, got {output_shape!r}",
        )
    dst = np.asarray(dst_corners, dtype=np.float64).reshape(4, 2)
    h_src, w_src = image.shape[:2]

    out = np.zeros((h_out, w_out, 4), dtype=np.uint8)
    n = int(samples_per_axis)
    u_axis = np.linspace(0.0, 1.0, n)
    v_axis = np.linspace(0.0, 1.0, n)
    for u in u_axis:
        for v in v_axis:
            x = (
                (1 - u) * (1 - v) * dst[0, 0]
                + u * (1 - v) * dst[1, 0]
                + u * v * dst[2, 0]
                + (1 - u) * v * dst[3, 0]
            )
            y = (
                (1 - u) * (1 - v) * dst[0, 1]
                + u * (1 - v) * dst[1, 1]
                + u * v * dst[2, 1]
                + (1 - u) * v * dst[3, 1]
            )
            ix = int(round(x))
            iy = int(round(y))
            if not (0 <= ix < w_out and 0 <= iy < h_out):
                continue
            sx = u * (w_src - 1)
            sy = v * (h_src - 1)
            sample = _bilinear_sample(
                image,
                np.array([sx], dtype=np.float64),
                np.array([sy], dtype=np.float64),
            )
            out[iy, ix] = sample[0]
    return out
