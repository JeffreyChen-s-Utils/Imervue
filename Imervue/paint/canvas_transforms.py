"""Pure-numpy canvas-wide transform helpers.

Five operations that rearrange every pixel of an HxWx4 RGBA buffer
(or any 2-D / 3-D array) without resampling:

* :func:`rotate_90_ccw` — 90° counter-clockwise (w/h swap)
* :func:`rotate_90_cw`  — 90° clockwise (w/h swap)
* :func:`rotate_180`    — 180° (shape unchanged)
* :func:`flip_horizontal` — mirror across the vertical axis
* :func:`flip_vertical`   — mirror across the horizontal axis

Each helper returns a fresh contiguous array — the caller can drop
it back into ``layer.image`` (or any other buffer) without worrying
about strided views interacting badly with downstream numpy slicing.

The :class:`Imervue.paint.document.PaintDocument` wraps these in
``transform_canvas(action=…)`` so a canvas rotation re-shapes every
layer image, every layer mask, and the active selection in lock-step.
"""
from __future__ import annotations

import numpy as np

CANVAS_TRANSFORM_ACTIONS = (
    "rotate_90_ccw",
    "rotate_90_cw",
    "rotate_180",
    "flip_horizontal",
    "flip_vertical",
)


def rotate_90_ccw(arr: np.ndarray) -> np.ndarray:
    """Rotate ``arr`` 90° counter-clockwise."""
    return np.ascontiguousarray(np.rot90(arr, k=1))


def rotate_90_cw(arr: np.ndarray) -> np.ndarray:
    """Rotate ``arr`` 90° clockwise."""
    return np.ascontiguousarray(np.rot90(arr, k=-1))


def rotate_180(arr: np.ndarray) -> np.ndarray:
    """Rotate ``arr`` 180°. Shape is preserved."""
    return np.ascontiguousarray(np.rot90(arr, k=2))


def flip_horizontal(arr: np.ndarray) -> np.ndarray:
    """Mirror ``arr`` across the vertical axis (left ↔ right)."""
    return np.ascontiguousarray(np.fliplr(arr))


def flip_vertical(arr: np.ndarray) -> np.ndarray:
    """Mirror ``arr`` across the horizontal axis (top ↔ bottom)."""
    return np.ascontiguousarray(np.flipud(arr))


def apply_canvas_transform(arr: np.ndarray, action: str) -> np.ndarray:
    """Dispatch by ``action`` name. Useful as a single entry point for
    the ``PaintDocument.transform_canvas`` shell — keeps the document
    method short and lets the menu layer pass action strings around
    without an enum import."""
    if action == "rotate_90_ccw":
        return rotate_90_ccw(arr)
    if action == "rotate_90_cw":
        return rotate_90_cw(arr)
    if action == "rotate_180":
        return rotate_180(arr)
    if action == "flip_horizontal":
        return flip_horizontal(arr)
    if action == "flip_vertical":
        return flip_vertical(arr)
    raise ValueError(
        f"unknown canvas-transform action {action!r}; "
        f"expected one of {CANVAS_TRANSFORM_ACTIONS}",
    )
