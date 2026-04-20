"""
Focus stacking — fuse multiple focus planes into a single all-in-focus image.

The algorithm is:

1. **Align** each frame to the first frame using ECC (enhanced correlation
   coefficient) for sub-pixel stability; falls back to no alignment when
   ECC does not converge (e.g. very noisy stacks).
2. **Measure focus** per-pixel with the Laplacian variance over a small
   window — a standard proxy for local sharpness.
3. **Fuse** by picking the pixel from whichever input frame has the
   highest local sharpness score at that location, then softening the
   boundaries with a gaussian blend to avoid seams.

Typical use cases: macro photography where the depth of field is too
shallow to cover the subject in one shot, product photography with
focus bracketing, and landscape near-far stacks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.focus_stack")


@dataclass
class FocusStackOptions:
    """Parameters for the focus stacking pipeline."""

    align: bool = True
    focus_window: int = 5        # Laplacian variance window (odd, 3-15)
    blend_sigma: float = 4.0     # gaussian blend across the selection mask


def _load_rgb(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _align_ecc(
    reference_gray: np.ndarray, moving_gray: np.ndarray, moving_rgb: np.ndarray,
) -> np.ndarray:
    import cv2
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-4)
    try:
        _cc, warp = cv2.findTransformECC(
            reference_gray, moving_gray, warp,
            motionType=cv2.MOTION_AFFINE, criteria=criteria,
        )
    except cv2.error:
        return moving_rgb
    h, w = reference_gray.shape
    aligned = cv2.warpAffine(
        moving_rgb, warp, (w, h),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return aligned


def _focus_map(gray: np.ndarray, window: int) -> np.ndarray:
    import cv2
    lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    lap_sq = lap * lap
    kernel = np.ones((window, window), dtype=np.float32) / (window * window)
    return cv2.filter2D(lap_sq, -1, kernel)


def stack_focus(
    paths: list[str | Path], options: FocusStackOptions | None = None,
) -> np.ndarray:
    """Focus-stack the images, returning HxWx4 RGBA uint8."""
    import cv2

    opts = options or FocusStackOptions()
    if len(paths) < 2:
        raise ValueError("Focus stacking needs at least two images")
    rgbs = [_load_rgb(p) for p in paths]
    first_shape = rgbs[0].shape[:2]
    for i, img in enumerate(rgbs):
        if img.shape[:2] != first_shape:
            raise ValueError(
                f"image {i} shape {img.shape[:2]} != first shape {first_shape}"
            )

    if opts.align:
        reference_gray = cv2.cvtColor(rgbs[0], cv2.COLOR_RGB2GRAY)
        aligned = [rgbs[0]]
        for img in rgbs[1:]:
            g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            aligned.append(_align_ecc(reference_gray, g, img))
        rgbs = aligned

    window = max(3, int(opts.focus_window) | 1)
    focus_maps = np.stack(
        [_focus_map(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), window) for img in rgbs],
        axis=0,
    )
    best_idx = np.argmax(focus_maps, axis=0).astype(np.int32)

    stack = np.stack(rgbs, axis=0).astype(np.float32)
    h, w, _ = rgbs[0].shape
    out = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(len(rgbs)):
        mask = (best_idx == i).astype(np.float32)
        if opts.blend_sigma > 0.0:
            mask = cv2.GaussianBlur(mask, (0, 0), opts.blend_sigma)
        out += stack[i] * mask[..., None]

    np.clip(out, 0.0, 255.0, out=out)
    rgb_u8 = out.astype(np.uint8)
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = rgb_u8
    rgba[..., 3] = 255
    return rgba
