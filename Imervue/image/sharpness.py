"""Image sharpness scoring for auto-culling.

The variance of an image's Laplacian is the classic blur metric: a sharp image
has strong second-derivative responses at edges (high variance), while a blurry
one is smooth (low variance). Scoring downscaled grayscale keeps the numbers
comparable across images.

All functions are pure NumPy and unit-tested; the orchestrator that loads files
and writes cull state lives in :mod:`Imervue.library.auto_cull`.
"""
from __future__ import annotations

import numpy as np

DEFAULT_BLUR_THRESHOLD = 100.0
_RGB_CHANNELS = 3
_LUMA_WEIGHTS = (0.299, 0.587, 0.114)
_LAPLACIAN_CENTRE = 4.0


def to_luma(arr: np.ndarray) -> np.ndarray:
    """Convert an image array to a 2-D float luma plane (grayscale passes through)."""
    data = np.asarray(arr)
    if data.ndim == 2:
        return data.astype(np.float64)
    rgb = data[..., :_RGB_CHANNELS].astype(np.float64)
    return rgb @ np.array(_LUMA_WEIGHTS, dtype=np.float64)


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of the 4-neighbour discrete Laplacian — higher means sharper."""
    g = np.asarray(gray, dtype=np.float64)
    if g.ndim != 2 or g.size == 0:
        return 0.0
    up = np.pad(g, ((1, 0), (0, 0)), mode="edge")[:-1]
    down = np.pad(g, ((0, 1), (0, 0)), mode="edge")[1:]
    left = np.pad(g, ((0, 0), (1, 0)), mode="edge")[:, :-1]
    right = np.pad(g, ((0, 0), (0, 1)), mode="edge")[:, 1:]
    laplacian = up + down + left + right - _LAPLACIAN_CENTRE * g
    return float(laplacian.var())


def sharpness_score(arr: np.ndarray) -> float:
    """Sharpness score for an image array (Laplacian variance of its luma)."""
    return laplacian_variance(to_luma(arr))


def select_blurry(
    scores_by_path: list[tuple[str, float]],
    threshold: float = DEFAULT_BLUR_THRESHOLD,
) -> list[str]:
    """Return the paths whose sharpness score falls below *threshold*."""
    return [path for path, score in scores_by_path if score < threshold]
