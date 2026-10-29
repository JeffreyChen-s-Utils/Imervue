"""
比對對話框的影像運算
Compare dialog image math: bounded RGBA loading, overlay blend, gain-boosted
difference and the ndarray-to-QImage copy.
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtGui import QImage

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import as_shown_8bit


def _load_rgba_array(path: str, max_edge: int = 2048) -> np.ndarray | None:
    """Load an image and return it as an RGBA uint8 ndarray, downscaled if huge.

    We cap the long edge at ``max_edge`` so overlay/difference operations stay
    fast on very large source images — the compare UI itself never shows more
    than ~1000 px on screen anyway.
    """
    try:
        with Image.open(path) as src:
            im = as_shown_8bit(src)
            w, h = im.size
            long_edge = max(w, h)
            if long_edge > max_edge:
                scale = max_edge / long_edge
                im = im.resize(
                    (int(w * scale), int(h * scale)),
                    Image.Resampling.LANCZOS,
                )
            return np.asarray(im, dtype=np.uint8)
    except IMAGE_READ_ERRORS:
        return None


def _match_sizes(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Resize ``b`` to match ``a``'s shape via PIL's high-quality Lanczos."""
    if a.shape == b.shape:
        return a, b
    target_h, target_w = a.shape[:2]
    im_b = Image.fromarray(b, mode="RGBA").resize(
        (target_w, target_h), Image.Resampling.LANCZOS,
    )
    return a, np.asarray(im_b, dtype=np.uint8)


def compute_overlay(a: np.ndarray, b: np.ndarray, alpha: float) -> np.ndarray:
    """Blend ``a`` and ``b`` by alpha (0 → a, 1 → b), ignoring alpha channels."""
    a, b = _match_sizes(a, b)
    alpha = float(max(0.0, min(1.0, alpha)))
    out = a.astype(np.float32) * (1.0 - alpha) + b.astype(np.float32) * alpha
    result = np.clip(out, 0, 255).astype(np.uint8)
    # Force opaque alpha — the overlay is a preview, not a transparent asset
    result[..., 3] = 255
    return result


def compute_difference(a: np.ndarray, b: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """Per-pixel |a - b| on RGB, scaled by ``gain`` and clipped to [0, 255]."""
    a, b = _match_sizes(a, b)
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))[:, :, :3]
    scaled = np.clip(diff.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    # Build a solid-alpha RGBA image for QImage consumption
    h, w, _ = scaled.shape
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[..., :3] = scaled
    out[..., 3] = 255
    return out


def _ndarray_to_qimage(arr: np.ndarray) -> QImage:
    """Copy an RGBA ndarray into a fresh QImage (safe against Python GC)."""
    h, w, _ = arr.shape
    # RGBA → QImage.Format_RGBA8888 lays out bytes the same way
    qimg = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return qimg.copy()
