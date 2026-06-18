"""Statistical image stacking — collapse an aligned burst into one frame.

A burst shot from a fixed position (tripod) can be reduced to a single
image by combining the frames pixel-wise. Unlike HDR merge (exposure
fusion) and focus stacking (per-pixel sharpness selection), this is a
pure-NumPy statistical reduction with no OpenCV dependency, so it ships
in the main program.

Modes:

* ``mean``   — average every frame. Smooths motion (waterfalls, clouds,
  crowds) into a long-exposure look and averages away shot noise.
* ``median`` — per-pixel median. Drops transient objects that appear in
  only a minority of frames (passing people / cars) and is robust to
  hot pixels and outliers.
* ``max``    — per-pixel maximum (lighten). Accumulates the brightest
  contribution of every frame: star trails, fireworks, light painting.
* ``min``    — per-pixel minimum (darken). Keeps the darkest sample,
  dropping bright transients.

Inputs are assumed already aligned (same camera position). Run the
images through a tripod / Auto-Straighten first if they are not — this
module deliberately does no registration so it stays dependency-free.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image

STACK_MEAN = "mean"
STACK_MEDIAN = "median"
STACK_MAX = "max"
STACK_MIN = "min"
STACK_SIGMA = "sigma"
STACK_MODES = (STACK_MEAN, STACK_MEDIAN, STACK_MAX, STACK_MIN, STACK_SIGMA)

_MIN_FRAMES = 2
_RGB_CHANNELS = 3
_OPAQUE = 255
_KAPPA = 2.5


def blend_stack(frames: Sequence[np.ndarray], mode: str) -> np.ndarray:
    """Reduce same-shape HxWx3 uint8 *frames* to one HxWx3 uint8 frame.

    The pure statistical core — no file IO, no alpha handling — so it is
    cheap to unit-test on synthetic arrays.
    """
    if mode not in STACK_MODES:
        raise ValueError(f"unknown stack mode {mode!r}; expected one of {STACK_MODES}")
    if len(frames) < _MIN_FRAMES:
        raise ValueError(f"stacking needs at least {_MIN_FRAMES} frames")
    first = frames[0]
    if first.ndim != _RGB_CHANNELS or first.shape[2] != _RGB_CHANNELS:
        raise ValueError(f"expected HxWx3 frames, got {first.shape}")
    for i, frame in enumerate(frames):
        if frame.shape != first.shape:
            raise ValueError(f"frame {i} shape {frame.shape} != first {first.shape}")
    return _reduce(frames, mode)


def _reduce(frames: Sequence[np.ndarray], mode: str) -> np.ndarray:
    if mode == STACK_MEDIAN:
        # Median is the one mode that needs every frame resident at once.
        return np.median(np.stack(frames, axis=0), axis=0).round().astype(np.uint8)
    if mode == STACK_SIGMA:
        return _sigma_clip(frames)
    if mode == STACK_MEAN:
        acc = np.zeros(frames[0].shape, dtype=np.float64)
        for frame in frames:
            acc += frame
        return (acc / len(frames)).round().astype(np.uint8)
    # max / min reduce incrementally — only two frames resident at a time.
    reducer = np.maximum if mode == STACK_MAX else np.minimum
    out = frames[0].copy()
    for frame in frames[1:]:
        out = reducer(out, frame)
    return out


def _sigma_clip(frames: Sequence[np.ndarray]) -> np.ndarray:
    """Average the stack after rejecting per-pixel outliers beyond kappa-sigma.

    Drops satellite/airplane trails, cosmic rays and brief passers-by that a
    plain mean would smear in, falling back to the median where every sample
    was rejected.
    """
    stacked = np.stack(frames, axis=0).astype(np.float32)
    median = np.median(stacked, axis=0)
    spread = stacked.std(axis=0)
    low = median - _KAPPA * spread
    high = median + _KAPPA * spread
    keep = (stacked >= low) & (stacked <= high)
    kept_sum = np.where(keep, stacked, 0.0).sum(axis=0)
    kept_count = keep.sum(axis=0)
    averaged = np.where(kept_count > 0, kept_sum / np.maximum(kept_count, 1), median)
    return np.clip(np.rint(averaged), 0, 255).astype(np.uint8)


def _load_rgb(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def stack_images(paths: Sequence[str | Path], mode: str) -> np.ndarray:
    """Load *paths*, statistically blend them, return HxWx4 RGBA uint8."""
    if len(paths) < _MIN_FRAMES:
        raise ValueError(f"stacking needs at least {_MIN_FRAMES} images")
    frames = [_load_rgb(p) for p in paths]
    rgb = blend_stack(frames, mode)
    h, w = rgb.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = _OPAQUE
    return rgba
