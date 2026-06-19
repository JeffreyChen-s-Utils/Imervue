"""Copy-move forgery detection.

Flags regions that were cloned from elsewhere in the same image (a classic
"paint out / stamp over" edit that Error Level Analysis can miss). Overlapping
blocks are reduced to a compact feature, sorted lexicographically, and adjacent
near-identical features lying far apart spatially are marked as a matched
clone pair.

Pure NumPy: an O(n log n) sort instead of an O(n²) all-pairs comparison, with
flat (low-variance) blocks skipped so smooth backgrounds don't false-positive.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.sharpness import to_luma

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_OPAQUE = 255
_BLOCK = 16
_POOL = 4
_STEP = 8
_VARIANCE_MIN = 25.0
_FEATURE_TOLERANCE = 6
_DIM_FACTOR = 0.5
_MARK_COLOR = (255, 0, 0)
DEFAULT_MIN_DISTANCE = 24


def _validate(arr: np.ndarray) -> None:
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] not in (_RGB_CHANNELS, _RGBA_CHANNELS):
        raise ValueError(f"expected HxWx3/4 uint8 image, got {arr.shape}")


def _block_features(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    feats: list[np.ndarray] = []
    positions: list[tuple[int, int]] = []
    h, w = gray.shape
    for y in range(0, h - _BLOCK + 1, _STEP):
        for x in range(0, w - _BLOCK + 1, _STEP):
            patch = gray[y:y + _BLOCK, x:x + _BLOCK]
            if patch.std() < _VARIANCE_MIN:
                continue
            pooled = patch.reshape(_POOL, _BLOCK // _POOL, _POOL, _BLOCK // _POOL).mean(
                axis=(1, 3))
            feats.append(np.rint(pooled).astype(np.int16).ravel())
            positions.append((y, x))
    if not feats:
        return np.empty((0, _POOL * _POOL), dtype=np.int16), np.empty((0, 2), dtype=np.int64)
    return np.array(feats), np.array(positions)


def _matched_blocks(feats: np.ndarray, positions: np.ndarray, min_distance: int) -> np.ndarray:
    flagged = np.zeros(len(feats), dtype=bool)
    order = np.lexsort(feats.T[::-1])
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        if np.abs(feats[a] - feats[b]).sum() > _FEATURE_TOLERANCE:
            continue
        dy, dx = positions[a] - positions[b]
        if np.hypot(dy, dx) >= min_distance:
            flagged[a] = flagged[b] = True
    return flagged


def copy_move_map(arr: np.ndarray, min_distance: int = DEFAULT_MIN_DISTANCE) -> np.ndarray:
    """Return an HxWx4 RGBA overlay with cloned regions marked in red."""
    _validate(arr)
    gray = to_luma(arr)
    feats, positions = _block_features(gray)
    flagged = _matched_blocks(feats, positions, max(0, int(min_distance)))

    mask = np.zeros(gray.shape, dtype=bool)
    for (y, x), is_flagged in zip(positions, flagged, strict=True):
        if is_flagged:
            mask[y:y + _BLOCK, x:x + _BLOCK] = True

    out = np.empty((*gray.shape, _RGBA_CHANNELS), dtype=np.uint8)
    out[..., :3] = np.clip(arr[..., :3].astype(np.float32) * _DIM_FACTOR, 0, 255).astype(
        np.uint8)
    out[..., 3] = _OPAQUE
    out[mask, :3] = _MARK_COLOR
    return out
