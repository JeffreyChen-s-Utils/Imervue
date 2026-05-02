"""Drop-a-pose workflow — paste a pose silhouette as a fresh layer.

The :class:`Imervue.paint.material_library.MaterialIndex` already
indexes pose silhouettes (PNGs in the ``pose`` category). This module
is the verbs that bridge from "user clicked a pose thumbnail" to
"there's a new layer underneath the active layer with the silhouette
fitted into the canvas". Pure-numpy / Qt-free; the UI plumbing lives
in :mod:`paint_workspace`.

Design notes
------------

* A pose drop creates a *new* layer rather than mutating the active
  one. Pose silhouettes are reference imagery the artist sketches
  over and then deletes; mixing them into the line layer would force
  a flatten step nobody asked for.
* The pose is auto-fitted into the canvas with a configurable
  margin so even a small canvas gets a proportionally-correct figure.
* Aspect ratio is preserved — the fit picks the smaller of
  width / height ratios so the silhouette never stretches.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_POSE_MARGIN = 0.1   # leave 10 % canvas border around the figure
MIN_POSE_PIXELS = 8


def fit_pose_to_canvas(
    pose_image: np.ndarray,
    canvas_shape: tuple[int, int],
    *,
    margin: float = DEFAULT_POSE_MARGIN,
) -> np.ndarray:
    """Return a canvas-sized RGBA buffer with ``pose_image`` centred.

    ``pose_image`` must be HxWx4 uint8. The output has shape
    ``canvas_shape + (4,)`` with the pose scaled-and-centred and the
    surrounding pixels left transparent so compositing as a new
    layer doesn't bake a frame into the line work.

    ``margin`` (in [0, 0.5)) controls how much of the canvas stays
    empty around the figure. The fit preserves aspect ratio by
    picking the smaller of width / height ratios.
    """
    if pose_image.ndim != 3 or pose_image.shape[2] != 4 or pose_image.dtype != np.uint8:
        raise ValueError(
            f"pose_image must be HxWx4 uint8 RGBA, "
            f"got {pose_image.shape} {pose_image.dtype}",
        )
    if not 0.0 <= margin < 0.5:
        raise ValueError(
            f"margin must be in [0, 0.5), got {margin!r}",
        )
    canvas_h, canvas_w = int(canvas_shape[0]), int(canvas_shape[1])
    if canvas_h <= 0 or canvas_w <= 0:
        raise ValueError(
            f"canvas_shape must be positive, got {canvas_shape!r}",
        )
    pose_h, pose_w = pose_image.shape[:2]
    if pose_h < MIN_POSE_PIXELS or pose_w < MIN_POSE_PIXELS:
        raise ValueError(
            f"pose image too small: {pose_w}×{pose_h} (min {MIN_POSE_PIXELS})",
        )
    # Available drawing area shrinks by margin on each side.
    avail_w = canvas_w * (1.0 - 2.0 * margin)
    avail_h = canvas_h * (1.0 - 2.0 * margin)
    scale = min(avail_w / pose_w, avail_h / pose_h)
    # Final pose dimensions after fit; never smaller than 1 pixel.
    out_w = max(1, int(round(pose_w * scale)))
    out_h = max(1, int(round(pose_h * scale)))
    resized = _resize_rgba_nearest(pose_image, (out_h, out_w))
    out = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    # Centre placement — leftover pixel after rounding goes to the right.
    x0 = max(0, (canvas_w - out_w) // 2)
    y0 = max(0, (canvas_h - out_h) // 2)
    x1 = min(canvas_w, x0 + out_w)
    y1 = min(canvas_h, y0 + out_h)
    src_w = x1 - x0
    src_h = y1 - y0
    if src_w > 0 and src_h > 0:
        out[y0:y1, x0:x1, :] = resized[:src_h, :src_w, :]
    return out


def load_pose_image(path: str | Path) -> np.ndarray:
    """Read an image from ``path`` and return it as HxWx4 uint8 RGBA.

    Late-imports PIL so callers that never drop poses don't pay for
    the import. Greyscale and RGB sources are widened to RGBA with
    full opacity; transparent PNGs pass through unchanged.
    """
    from PIL import Image
    with Image.open(path) as src:
        rgba = src.convert("RGBA")
        return np.array(rgba, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resize_rgba_nearest(
    image: np.ndarray, target_shape: tuple[int, int],
) -> np.ndarray:
    """Nearest-neighbour resample of an HxWx4 RGBA buffer.

    Nearest is intentional — pose silhouettes have crisp edges and
    bilinear resampling would soften them into a halo that bleeds
    into the artist's line work. For reference imagery, nearest is
    the right default.
    """
    src_h, src_w = image.shape[:2]
    dst_h, dst_w = int(target_shape[0]), int(target_shape[1])
    if dst_h <= 0 or dst_w <= 0:
        return np.zeros((max(1, dst_h), max(1, dst_w), 4), dtype=np.uint8)
    if (dst_h, dst_w) == (src_h, src_w):
        return image.copy()
    # Compute source indices via broadcasting.
    ys = (np.arange(dst_h) * src_h / dst_h).astype(np.int64)
    xs = (np.arange(dst_w) * src_w / dst_w).astype(np.int64)
    ys = np.clip(ys, 0, src_h - 1)
    xs = np.clip(xs, 0, src_w - 1)
    return image[ys[:, None], xs[None, :], :]
