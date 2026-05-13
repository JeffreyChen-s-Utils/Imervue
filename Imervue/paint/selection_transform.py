"""Pure-numpy affine transform for selected pixels.

Photoshop / raster paint apps's "free transform on a selection" operation —
scale, rotate, and translate the pixels under the active selection
without resampling the rest of the layer.

Workflow ``transform_selection`` follows:

1. Find the centre (``anchor``) — caller-provided or derived from
   the selection bounding box.
2. Cut the layer pixels under the selection into a buffer; the
   original locations become fully transparent.
3. For every output pixel, run the inverse affine transform to
   find a source coordinate inside the cut and sample bilinearly.
4. Combine: untouched layer pixels stay where they were; the warped
   selection pixels appear at their new location.
5. The new selection mask is a thresholded bilinear sample of the
   original mask itself, so a feathered edge stays roughly the
   same shape after rotation.

Pure numpy / Qt-free.
"""
from __future__ import annotations

import math

import numpy as np

# An ``identity transform`` is detected by ``math.isclose`` on these
# arguments and short-circuited. ``isclose`` covers tiny accumulated
# drift from repeated transform pushes; the default relative tolerance
# (1e-9) keeps a deliberate ``scale = 1.0 + 1e-9`` from being silently
# treated as identity.
_IDENTITY_SCALE = 1.0
_IDENTITY_ANGLE = 0.0


def transform_selection(
    layer_image: np.ndarray,
    selection_mask: np.ndarray,
    *,
    scale: float = 1.0,
    angle_deg: float = 0.0,
    dx: float = 0.0,
    dy: float = 0.0,
    anchor: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply scale + rotate + translate to the selected pixels.

    Returns ``(new_image, new_selection_mask)``. The inputs are not
    mutated.

    * ``scale`` — uniform scale factor (must be > 0)
    * ``angle_deg`` — rotation in degrees (counter-clockwise)
    * ``dx``, ``dy`` — translation in pixels (image coordinates)
    * ``anchor`` — pivot point in image coords; defaults to the
      bounding-box centre of the selection
    """
    _check_image(layer_image)
    _check_mask(selection_mask, layer_image.shape[:2])
    if scale <= 0.0:
        raise ValueError(f"scale must be > 0, got {scale}")

    if not selection_mask.any():
        return layer_image.copy(), selection_mask.copy()

    if (
        math.isclose(scale, _IDENTITY_SCALE)
        and math.isclose(angle_deg, _IDENTITY_ANGLE)
        and math.isclose(dx, 0.0) and math.isclose(dy, 0.0)
    ):
        # Pure identity — skip the warp pass entirely.
        return layer_image.copy(), selection_mask.copy()

    if anchor is None:
        ys_sel, xs_sel = np.nonzero(selection_mask)
        cx = (xs_sel.min() + xs_sel.max()) / 2.0
        cy = (ys_sel.min() + ys_sel.max()) / 2.0
    else:
        cx, cy = float(anchor[0]), float(anchor[1])

    h, w = layer_image.shape[:2]
    ys_out, xs_out = np.indices((h, w), dtype=np.float32)
    dxp = xs_out - (cx + dx)
    dyp = ys_out - (cy + dy)
    inv_scale = 1.0 / scale
    rad = np.radians(-angle_deg)
    cos_a = float(np.cos(rad))
    sin_a = float(np.sin(rad))
    rot_x = (cos_a * dxp - sin_a * dyp) * inv_scale
    rot_y = (sin_a * dxp + cos_a * dyp) * inv_scale
    xs_src = rot_x + cx
    ys_src = rot_y + cy

    cut = np.zeros_like(layer_image)
    cut[selection_mask] = layer_image[selection_mask]
    sampled = _bilinear_sample_rgba(cut, xs_src, ys_src)

    sel_f = selection_mask.astype(np.float32)
    sel_sampled = _bilinear_sample_scalar(sel_f, xs_src, ys_src)
    new_selection = sel_sampled > 0.5

    new_image = layer_image.copy()
    new_image[selection_mask] = (0, 0, 0, 0)
    new_image[new_selection] = sampled[new_selection]
    return new_image, new_selection


# ---------------------------------------------------------------------------
# Bilinear samplers
# ---------------------------------------------------------------------------


def _bilinear_sample_rgba(
    image: np.ndarray, xs: np.ndarray, ys: np.ndarray,
) -> np.ndarray:
    """Bilinearly sample an HxWx4 uint8 RGBA at fractional (xs, ys).

    Out-of-bounds pixels return ``(0, 0, 0, 0)``.
    """
    h, w = image.shape[:2]
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1

    fx = (xs - x0).astype(np.float32)[..., None]
    fy = (ys - y0).astype(np.float32)[..., None]

    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y1, 0, h - 1)

    img_f = image.astype(np.float32)
    v00 = img_f[y0c, x0c]
    v01 = img_f[y0c, x1c]
    v10 = img_f[y1c, x0c]
    v11 = img_f[y1c, x1c]

    v0 = v00 * (1.0 - fx) + v01 * fx
    v1 = v10 * (1.0 - fx) + v11 * fx
    blended = v0 * (1.0 - fy) + v1 * fy

    in_bounds = (x0 >= 0) & (x1 < w) & (y0 >= 0) & (y1 < h)
    blended[~in_bounds] = 0.0
    return np.clip(blended, 0.0, 255.0).astype(np.uint8)


def _bilinear_sample_scalar(
    arr: np.ndarray, xs: np.ndarray, ys: np.ndarray,
) -> np.ndarray:
    """Bilinearly sample an HxW scalar field. Out-of-bounds → 0.0."""
    h, w = arr.shape[:2]
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    fx = (xs - x0).astype(np.float32)
    fy = (ys - y0).astype(np.float32)

    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y1, 0, h - 1)

    arr_f = arr.astype(np.float32)
    v00 = arr_f[y0c, x0c]
    v01 = arr_f[y0c, x1c]
    v10 = arr_f[y1c, x0c]
    v11 = arr_f[y1c, x1c]
    v0 = v00 * (1.0 - fx) + v01 * fx
    v1 = v10 * (1.0 - fx) + v11 * fx
    out = v0 * (1.0 - fy) + v1 * fy
    in_bounds = (x0 >= 0) & (x1 < w) & (y0 >= 0) & (y1 < h)
    out[~in_bounds] = 0.0
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _check_image(image: np.ndarray) -> None:
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"layer_image must be HxWx4 uint8 RGBA, "
            f"got {image.shape} {image.dtype}",
        )


def _check_mask(mask: np.ndarray, shape: tuple[int, int]) -> None:
    if mask.shape != shape:
        raise ValueError(
            f"selection_mask shape {mask.shape} does not match "
            f"layer {shape}",
        )
    if mask.dtype != np.bool_:
        raise ValueError(
            f"selection_mask must be bool, got dtype {mask.dtype}",
        )
