"""Pure-numpy transition effects for the MP4 slideshow.

Generalises the crossfade in :mod:`slideshow_mp4` into a small library of
deterministic, frame-by-frame transitions: ``fade`` (linear crossfade),
``dissolve`` (an ordered-dither pixel reveal that is stable across frames so
it doesn't flicker), four directional ``slide_*`` pushes, and two ``wipe_*``
hard reveals.

:func:`transition_frame` takes two equal-shaped ``HxWx3`` uint8 frames and a
progress in ``[0, 1]`` (``0`` = the previous frame, ``1`` = the next) and
returns the composited frame. No Qt, no I/O — easy to unit-test.
"""
from __future__ import annotations

import numpy as np

TRANSITIONS: tuple[str, ...] = (
    "fade", "dissolve",
    "slide_left", "slide_right", "slide_up", "slide_down",
    "wipe_left", "wipe_right",
)

# Recursive 8x8 Bayer matrix → per-pixel reveal thresholds in [0, 1). Tiled
# across the frame, a pixel switches to the next image once progress passes its
# threshold; because the matrix is fixed, the reveal is stable frame-to-frame.
_BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32) / 64.0


def transition_frame(
    prev: np.ndarray, nxt: np.ndarray, transition: str, progress: float,
) -> np.ndarray:
    """Composite *prev* → *nxt* at *progress* using the named *transition*."""
    if prev.shape != nxt.shape:
        raise ValueError(
            f"transition frames must share a shape, got {prev.shape} vs {nxt.shape}",
        )
    p = float(max(0.0, min(1.0, progress)))
    if transition == "fade":
        return _fade(prev, nxt, p)
    if transition == "dissolve":
        return _dissolve(prev, nxt, p)
    if transition in ("slide_left", "slide_right", "slide_up", "slide_down"):
        return _slide(prev, nxt, p, transition)
    if transition in ("wipe_left", "wipe_right"):
        return _wipe(prev, nxt, p, transition)
    raise ValueError(f"unknown transition {transition!r}; see TRANSITIONS")


def _fade(a: np.ndarray, b: np.ndarray, p: float) -> np.ndarray:
    return (
        a.astype(np.float32) * (1.0 - p) + b.astype(np.float32) * p
    ).astype(np.uint8)


def _dissolve(a: np.ndarray, b: np.ndarray, p: float) -> np.ndarray:
    h, w = a.shape[:2]
    rows, cols = np.indices((h, w))
    revealed = (_BAYER8[rows % 8, cols % 8] < p)[..., None]
    return np.where(revealed, b, a)


def _slide(a: np.ndarray, b: np.ndarray, p: float, kind: str) -> np.ndarray:
    h, w = a.shape[:2]
    out = np.empty_like(a)
    if kind in ("slide_left", "slide_right"):
        shift = int(round(p * w))
        if kind == "slide_left":
            out[:, :w - shift] = a[:, shift:]
            out[:, w - shift:] = b[:, :shift]
        else:
            out[:, shift:] = a[:, :w - shift]
            out[:, :shift] = b[:, w - shift:]
        return out
    shift = int(round(p * h))
    if kind == "slide_up":
        out[:h - shift] = a[shift:]
        out[h - shift:] = b[:shift]
    else:
        out[shift:] = a[:h - shift]
        out[:shift] = b[h - shift:]
    return out


def _wipe(a: np.ndarray, b: np.ndarray, p: float, kind: str) -> np.ndarray:
    w = a.shape[1]
    split = int(round(p * w))
    out = a.copy()
    if kind == "wipe_left":
        out[:, :split] = b[:, :split]
    else:
        out[:, w - split:] = b[:, w - split:]
    return out
