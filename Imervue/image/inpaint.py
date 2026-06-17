"""Model-free diffusion inpainting (object removal / scratch fill).

Fills a masked region by relaxing it to the harmonic (Laplace) interpolation of
the surrounding pixels: known pixels are fixed boundary conditions and masked
pixels iterate toward the average of their neighbours. This is the pure-numpy
fallback — good for small holes, scratches and clean backgrounds — that a
generative LaMa/ONNX path (shipped as a plugin) can supersede for large or
textured regions. Qt/model-free, so it is fully unit-testable.
"""
from __future__ import annotations

import numpy as np

DEFAULT_ITERATIONS = 80
_MAX_BYTE = 255.0


def _validate(image: np.ndarray, mask: np.ndarray) -> None:
    if image.ndim != 3 or image.dtype != np.uint8:
        raise ValueError(f"image must be HxWxC uint8, got {image.shape} {image.dtype}")
    if mask.shape != image.shape[:2]:
        raise ValueError(
            f"mask shape {mask.shape} must match image {image.shape[:2]}")


def inpaint_diffusion(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    iterations: int = DEFAULT_ITERATIONS,
) -> np.ndarray:
    """Inpaint the ``True`` region of *mask* in *image* by neighbour diffusion.

    *image* is ``HxWxC`` uint8 (RGB or RGBA); *mask* is an ``HxW`` boolean array
    where ``True`` marks pixels to fill. Known pixels are held fixed, so the
    masked region relaxes to a smooth interpolation of its boundary. Edges use
    clamped (edge-replicated) neighbours so the fill never wraps across the
    image. An empty mask returns an unchanged copy.
    """
    _validate(image, mask)
    fill = np.asarray(mask, dtype=bool)
    out = image.astype(np.float64)
    if not fill.any():
        return image.copy()
    fill3 = fill[:, :, None]
    iterations = max(1, int(iterations))
    for _ in range(iterations):
        up = np.pad(out, ((1, 0), (0, 0), (0, 0)), mode="edge")[:-1]
        down = np.pad(out, ((0, 1), (0, 0), (0, 0)), mode="edge")[1:]
        left = np.pad(out, ((0, 0), (1, 0), (0, 0)), mode="edge")[:, :-1]
        right = np.pad(out, ((0, 0), (0, 1), (0, 0)), mode="edge")[:, 1:]
        neighbour_mean = (up + down + left + right) * 0.25
        out = np.where(fill3, neighbour_mean, out)
    return np.clip(out, 0.0, _MAX_BYTE).astype(np.uint8)
