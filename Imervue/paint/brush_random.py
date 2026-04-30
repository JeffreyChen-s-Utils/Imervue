"""Per-dab brush randomisation — scatter, color jitter, tilt rotation.

Three independent perturbations applied during a brush stroke; each
opt-in via the corresponding BrushSettings field:

* :func:`scatter_offset` — scrambles the (cx, cy) of each dab by a
  uniformly-random offset in a disc of radius ``scatter * size``.
* :func:`jitter_color` — perturbs the RGB color of each dab in HSV
  space (hue, saturation and value all shifted by a small random
  amount proportional to ``color_jitter``).
* :func:`tilt_rotation_radians` — derives a kernel-rotation angle
  from a pen-tilt vector. The brush kernel can then be rotated to
  follow the artist's wrist, the way a calligraphy nib does.

Pure numpy + math; the BrushStroke loop in brush_engine threads
its own RNG into these helpers so the same seed reproduces a
stroke pixel-for-pixel.
"""
from __future__ import annotations

import math

import numpy as np

from Imervue.paint.adjustments import _hsv_to_rgb, _rgb_to_hsv

# Limits — color jitter shifts hue by at most one full circle and
# attenuates / amplifies saturation + value by a bounded fraction.
_MAX_HUE_SHIFT_DEG = 60.0
_MAX_S_DELTA = 0.4
_MAX_V_DELTA = 0.3


def scatter_offset(
    size: int, scatter: float, rng: np.random.Generator,
) -> tuple[float, float]:
    """Return a random ``(dx, dy)`` offset for a single dab.

    ``scatter`` in ``[0, 1]`` is the offset radius as a fraction of
    ``size`` — 0 means "no scatter" (the helper short-circuits to
    ``(0, 0)``), 1 means up to a full brush-width displacement.
    """
    if scatter <= 0:
        return (0.0, 0.0)
    radius = float(size) * float(scatter)
    angle = float(rng.uniform(0.0, 2.0 * math.pi))
    r = float(rng.uniform(0.0, radius))
    return (r * math.cos(angle), r * math.sin(angle))


def jitter_color(
    color: tuple[int, int, int],
    color_jitter: float,
    rng: np.random.Generator,
) -> tuple[int, int, int]:
    """Return a per-dab perturbed RGB colour.

    ``color_jitter`` in ``[0, 1]`` scales the maximum hue shift,
    saturation delta and value delta. 0 short-circuits to the input
    colour; 1 lets the dab vary across a sizeable portion of HSV.
    """
    if color_jitter <= 0:
        return (int(color[0]), int(color[1]), int(color[2]))
    rgb = np.array(
        [[[color[0] / 255.0, color[1] / 255.0, color[2] / 255.0]]],
        dtype=np.float32,
    )
    hsv = _rgb_to_hsv(rgb)
    hue_shift = float(rng.uniform(-1.0, 1.0)) * _MAX_HUE_SHIFT_DEG * color_jitter
    s_delta = float(rng.uniform(-1.0, 1.0)) * _MAX_S_DELTA * color_jitter
    v_delta = float(rng.uniform(-1.0, 1.0)) * _MAX_V_DELTA * color_jitter
    hsv[..., 0] = (hsv[..., 0] + hue_shift) % 360.0
    hsv[..., 1] = np.clip(hsv[..., 1] + s_delta, 0.0, 1.0)
    hsv[..., 2] = np.clip(hsv[..., 2] + v_delta, 0.0, 1.0)
    rgb_out = _hsv_to_rgb(hsv)
    perturbed = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return (
        int(perturbed[0, 0, 0]),
        int(perturbed[0, 0, 1]),
        int(perturbed[0, 0, 2]),
    )


def tilt_rotation_radians(tilt_x: float, tilt_y: float) -> float:
    """Convert a pen-tilt vector to a kernel-rotation angle.

    ``tilt_x`` and ``tilt_y`` are in ``[-1, 1]`` per the
    :class:`PointerEvent` contract. ``(0, 0)`` produces ``0``
    radians (no rotation). The angle is the in-canvas projection of
    the tilt vector — what direction the stylus is leaning toward.
    """
    if abs(tilt_x) < 1e-9 and abs(tilt_y) < 1e-9:
        return 0.0
    return math.atan2(float(tilt_y), float(tilt_x))


def rotate_kernel(kernel: np.ndarray, angle_rad: float) -> np.ndarray:
    """Rotate a square 2-D brush kernel by ``angle_rad`` radians.

    Bilinearly resamples; out-of-bounds pixels wrap to zero. Returns
    a fresh contiguous float32 array of the same shape; the caller
    can drop it back into ``apply_dab`` as the active kernel.
    """
    if abs(angle_rad) < 1e-6:
        return np.ascontiguousarray(kernel, dtype=np.float32)
    if kernel.ndim != 2:
        raise ValueError(
            f"kernel must be 2-D, got shape {kernel.shape}",
        )
    h, w = kernel.shape
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    cos_a = math.cos(-angle_rad)
    sin_a = math.sin(-angle_rad)
    ys, xs = np.indices((h, w), dtype=np.float32)
    rel_x = xs - cx
    rel_y = ys - cy
    src_x = rel_x * cos_a - rel_y * sin_a + cx
    src_y = rel_x * sin_a + rel_y * cos_a + cy
    x0 = np.floor(src_x).astype(np.int32)
    y0 = np.floor(src_y).astype(np.int32)
    fx = (src_x - x0).astype(np.float32)
    fy = (src_y - y0).astype(np.float32)
    x1 = x0 + 1
    y1 = y0 + 1
    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y1, 0, h - 1)
    arr = kernel.astype(np.float32)
    v00 = arr[y0c, x0c]
    v01 = arr[y0c, x1c]
    v10 = arr[y1c, x0c]
    v11 = arr[y1c, x1c]
    v0 = v00 * (1.0 - fx) + v01 * fx
    v1 = v10 * (1.0 - fx) + v11 * fx
    out = v0 * (1.0 - fy) + v1 * fy
    # Permit samples exactly on the right / bottom edge so a perfect 90°
    # rotation (which lands the corner pixel on the boundary) doesn't
    # zero it out via the strict ``x1 < w`` / ``y1 < h`` check.
    in_bounds = (src_x >= 0) & (src_x <= w - 1) & (src_y >= 0) & (src_y <= h - 1)
    out[~in_bounds] = 0.0
    return np.ascontiguousarray(out)
