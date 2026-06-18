"""Object removal — flood-fill mask selection + diffusion inpainting.

Click a point, grow a colour-similar connected region into a mask, then fill it
with the model-free diffusion inpainter (:func:`Imervue.image.inpaint.inpaint_diffusion`).
A generative ONNX path (e.g. LaMa) can layer on later; shipping object removal
as a plugin already isolates that heavier dependency from the main viewer.

All functions here are pure NumPy — no Qt — so they are fully unit-testable.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.inpaint import DEFAULT_ITERATIONS, inpaint_diffusion

TOLERANCE_MIN = 0
TOLERANCE_MAX = 255
GROW_MAX = 20
_RGB_CHANNELS = 3
_NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _is_fillable(candidate: np.ndarray, mask: np.ndarray,
                 h: int, w: int, y: int, x: int) -> bool:
    return 0 <= y < h and 0 <= x < w and candidate[y, x] and not mask[y, x]


def flood_fill_mask(arr: np.ndarray, seed_x: int, seed_y: int,
                    tolerance: int) -> np.ndarray:
    """Boolean ``HxW`` mask of the colour-similar region connected to the seed.

    A pixel joins the region when every RGB channel is within *tolerance* of the
    seed colour and it is 4-connected to the seed. The seed itself is always
    included (it matches itself), so the mask is never empty for an in-bounds
    seed.
    """
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] < _RGB_CHANNELS:
        raise ValueError(f"expected HxWxC (C>=3) image, got {arr.shape}")
    rgb = arr[..., :_RGB_CHANNELS].astype(np.int16)
    h, w = rgb.shape[:2]
    sx = max(0, min(int(seed_x), w - 1))
    sy = max(0, min(int(seed_y), h - 1))
    tol = max(TOLERANCE_MIN, int(tolerance))
    candidate = np.abs(rgb - rgb[sy, sx]).max(axis=2) <= tol
    mask = np.zeros((h, w), dtype=bool)
    mask[sy, sx] = True
    stack = [(sy, sx)]
    while stack:
        y, x = stack.pop()
        for dy, dx in _NEIGHBOURS:
            ny, nx = y + dy, x + dx
            if _is_fillable(candidate, mask, h, w, ny, nx):
                mask[ny, nx] = True
                stack.append((ny, nx))
    return mask


def grow_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Dilate *mask* by *radius* pixels (4-connected) to cover soft edges."""
    grown = np.asarray(mask, dtype=bool)
    for _ in range(max(0, int(radius))):
        up = np.zeros_like(grown)
        up[:-1] = grown[1:]
        down = np.zeros_like(grown)
        down[1:] = grown[:-1]
        left = np.zeros_like(grown)
        left[:, :-1] = grown[:, 1:]
        right = np.zeros_like(grown)
        right[:, 1:] = grown[:, :-1]
        grown = grown | up | down | left | right
    return grown


def build_mask(arr: np.ndarray, seed_x: int, seed_y: int,
               tolerance: int, grow: int = 0) -> np.ndarray:
    """Flood-fill a mask at the seed, then grow it by *grow* pixels."""
    mask = flood_fill_mask(arr, seed_x, seed_y, tolerance)
    return grow_mask(mask, grow) if grow > 0 else mask


def remove_object(arr: np.ndarray, mask: np.ndarray,
                  iterations: int = DEFAULT_ITERATIONS) -> np.ndarray:
    """Fill the masked region of *arr* by diffusion inpainting."""
    return inpaint_diffusion(arr, mask, iterations=iterations)


def image_coord_from_click(wx: float, wy: float, label_w: int, label_h: int,
                           img_w: int, img_h: int) -> tuple[int, int] | None:
    """Map a click on a fit-scaled, centred preview to image pixel coords.

    Returns ``None`` when the click falls in the letterbox margin outside the
    drawn image.
    """
    if img_w <= 0 or img_h <= 0 or label_w <= 0 or label_h <= 0:
        return None
    scale = min(label_w / img_w, label_h / img_h)
    disp_w, disp_h = img_w * scale, img_h * scale
    off_x, off_y = (label_w - disp_w) / 2, (label_h - disp_h) / 2
    ix, iy = (wx - off_x) / scale, (wy - off_y) / scale
    if not (0 <= ix < img_w and 0 <= iy < img_h):
        return None
    return int(ix), int(iy)
