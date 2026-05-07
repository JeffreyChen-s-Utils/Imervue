"""Local Gaussian-blur dab for the blur tool.

The blur tool is a brush-style mutator: each pointer dab convolves
the canvas under the kernel with a Gaussian, weighted by the
kernel's alpha so the centre softens more than the rim. Pure-numpy
so the dispatcher can call it on every pointer move without dragging
in OpenCV at import time.
"""
from __future__ import annotations

import numpy as np

# A 3×3 separable Gaussian kernel — wide enough to blur, narrow
# enough that the per-dab cost stays bounded even at brush size 200.
_GAUSSIAN_1D = np.array([0.25, 0.5, 0.25], dtype=np.float32)


def _gaussian_blur_3x3(patch: np.ndarray) -> np.ndarray:
    """Separable 3×3 Gaussian on an HxWx3 float32 patch."""
    pad = np.pad(patch, ((1, 1), (1, 1), (0, 0)), mode="edge")
    horizontal = (
        _GAUSSIAN_1D[0] * pad[1:-1, :-2]
        + _GAUSSIAN_1D[1] * pad[1:-1, 1:-1]
        + _GAUSSIAN_1D[2] * pad[1:-1, 2:]
    )
    return (
        _GAUSSIAN_1D[0] * np.pad(horizontal, ((1, 0), (0, 0), (0, 0)),
                                 mode="edge")[:-1]
        + _GAUSSIAN_1D[1] * horizontal
        + _GAUSSIAN_1D[2] * np.pad(horizontal, ((0, 1), (0, 0), (0, 0)),
                                   mode="edge")[1:]
    )


def blur_dab(
    canvas: np.ndarray,
    cx: float,
    cy: float,
    kernel: np.ndarray,
    *,
    strength: float = 1.0,
    selection: np.ndarray | None = None,
) -> tuple[int, int, int, int]:
    """Apply one Gaussian-blur dab centred on ``(cx, cy)``.

    Returns the damage rect ``(x, y, w, h)`` of the patch that
    actually changed so the canvas can do a sub-region GPU upload.
    Empty rect when the dab fell entirely off-canvas.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"blur_dab expects HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    h, w = canvas.shape[:2]
    kh, kw = kernel.shape
    # ``apply_dab`` convention: origin = round(cx) - kw//2 spans
    # ``[origin, origin + kw)``. Even-sized kernels are biased to the
    # left/top (matches the brush engine).
    x0_full = int(round(cx)) - kw // 2
    y0_full = int(round(cy)) - kh // 2
    x0 = max(0, x0_full)
    y0 = max(0, y0_full)
    x1 = min(w, x0_full + kw)
    y1 = min(h, y0_full + kh)
    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0, 0)

    # Kernel slice that lines up with the clipped patch.
    kx0 = x0 - x0_full
    ky0 = y0 - y0_full
    kx1 = kx0 + (x1 - x0)
    ky1 = ky0 + (y1 - y0)
    patch = canvas[y0:y1, x0:x1, :3].astype(np.float32)
    kernel_slice = kernel[ky0:ky1, kx0:kx1].astype(np.float32)
    blurred = _gaussian_blur_3x3(patch)

    weight = np.clip(
        kernel_slice * float(max(0.0, min(1.0, strength))),
        0.0, 1.0,
    )[..., None]
    blended = patch * (1.0 - weight) + blurred * weight
    if selection is not None:
        sel_slice = selection[y0:y1, x0:x1].astype(np.float32)[..., None]
        blended = patch * (1.0 - sel_slice) + blended * sel_slice
    canvas[y0:y1, x0:x1, :3] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    return (x0, y0, x1 - x0, y1 - y0)
