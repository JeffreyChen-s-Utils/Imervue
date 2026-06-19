"""Background flattening — remove smooth gradients (light pollution / vignetting).

Fits a low-degree 2-D polynomial to the image's *background* (estimated from a
coarse grid of per-tile low percentiles, so a bright subject doesn't drag the
fit) and removes it. Subtractive removal evens out astro light-pollution
gradients and uneven copy-stand lighting; divisive removal corrects
multiplicative vignetting and flatbed-scan falloff.

Pure NumPy: a small least-squares polynomial fit, evaluated term-by-term at
full resolution so memory stays O(image).
"""
from __future__ import annotations

import numpy as np

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_EPS = 1e-6
_GRID = 12
_PERCENTILE = 25.0
DEFAULT_DEGREE = 2


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 image, got {arr.shape}")


def flatten_background(
    arr: np.ndarray, degree: int = DEFAULT_DEGREE, *, divide: bool = False,
) -> np.ndarray:
    """Remove a smooth polynomial gradient from *arr* (HxWx3/4 uint8)."""
    _validate(arr)
    degree = max(1, int(degree))
    rgb = arr[..., :3].astype(np.float32)
    out = np.empty_like(rgb)
    for channel in range(_RGB_CHANNELS):
        plane = rgb[..., channel]
        background = _fit_background(plane, degree)
        out[..., channel] = _correct(plane, background, divide)
    result = arr.copy()
    result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return result


def _correct(plane: np.ndarray, background: np.ndarray, divide: bool) -> np.ndarray:
    target = float(background.mean())
    if divide:
        return np.clip(plane / np.maximum(background, _EPS) * target, 0, 255)
    return np.clip(plane - background + target, 0, 255)


def _fit_background(plane: np.ndarray, degree: int) -> np.ndarray:
    xs, ys, vals = _sample_points(plane)
    coeffs, _residual, _rank, _sv = np.linalg.lstsq(
        _design(xs, ys, degree), vals, rcond=None)
    h, w = plane.shape
    grid_x = (np.arange(w) / max(1, w - 1) * 2.0 - 1.0)[None, :]
    grid_y = (np.arange(h) / max(1, h - 1) * 2.0 - 1.0)[:, None]
    return _eval_poly(coeffs, grid_x, grid_y, degree)


def _sample_points(plane: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, w = plane.shape
    edges_y = np.linspace(0, h, _GRID + 1).astype(int)
    edges_x = np.linspace(0, w, _GRID + 1).astype(int)
    xs, ys, vals = [], [], []
    for gy in range(_GRID):
        for gx in range(_GRID):
            tile = plane[edges_y[gy]:edges_y[gy + 1], edges_x[gx]:edges_x[gx + 1]]
            if tile.size == 0:
                continue
            cy = (edges_y[gy] + edges_y[gy + 1]) / 2.0
            cx = (edges_x[gx] + edges_x[gx + 1]) / 2.0
            ys.append(cy / max(1, h - 1) * 2.0 - 1.0)
            xs.append(cx / max(1, w - 1) * 2.0 - 1.0)
            vals.append(float(np.percentile(tile, _PERCENTILE)))
    return np.array(xs), np.array(ys), np.array(vals)


def _design(x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    cols = [
        (x ** i) * (y ** j)
        for i in range(degree + 1)
        for j in range(degree + 1 - i)
    ]
    return np.stack(cols, axis=1)


def _eval_poly(coeffs: np.ndarray, x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    out = np.zeros((y.shape[0], x.shape[1]), dtype=np.float32)
    k = 0
    for i in range(degree + 1):
        for j in range(degree + 1 - i):
            out = out + coeffs[k] * (x ** i) * (y ** j)
            k += 1
    return out
