"""AI segmentation — sky / foreground / background masks.

Primary path uses ``rembg`` (U²-Net) when installed for foreground
extraction. When unavailable, a deterministic heuristic fallback
segments the sky via a saturation/luminance HSV rule that's good enough
for landscape photos shot against a blue or grey sky.

Returns a HxW float32 mask in ``[0, 1]`` in both code paths so downstream
operations (sky replace, background blur) can treat them uniformly.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("Imervue.segmentation")

_SKY_MIN_HEIGHT_FRAC = 0.05


def _rembg_foreground_mask(arr: np.ndarray) -> np.ndarray | None:
    try:
        from rembg import remove
    except ImportError:
        return None
    try:
        cutout = remove(arr)
    except (OSError, ValueError) as err:
        logger.warning("rembg failed: %s", err)
        return None
    if cutout.ndim != 3 or cutout.shape[2] < 4:
        return None
    return cutout[..., 3].astype(np.float32) / 255.0


def foreground_mask(arr: np.ndarray) -> np.ndarray:
    """Return a HxW float32 mask: 1 = foreground, 0 = background."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("foreground_mask expects HxWx4 RGBA uint8")
    rembg_mask = _rembg_foreground_mask(arr)
    if rembg_mask is not None:
        return rembg_mask
    # Heuristic: high-saturation / mid-luminance = foreground.
    import cv2
    hsv = cv2.cvtColor(arr[..., [2, 1, 0]], cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1].astype(np.float32) / 255.0
    val = hsv[..., 2].astype(np.float32) / 255.0
    score = sat * (1.0 - np.abs(val - 0.5) * 1.2)
    return np.clip(score, 0.0, 1.0)


def sky_mask(arr: np.ndarray) -> np.ndarray:
    """Return a HxW float32 mask of pixels that look like sky.

    Heuristic: upper portion of the frame with low saturation OR blue hue
    and high value. Good enough for landscape photos; composable with the
    segmentation network when available.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("sky_mask expects HxWx4 RGBA uint8")
    import cv2
    hsv = cv2.cvtColor(arr[..., [2, 1, 0]], cv2.COLOR_BGR2HSV)
    hue = hsv[..., 0].astype(np.float32)
    sat = hsv[..., 1].astype(np.float32) / 255.0
    val = hsv[..., 2].astype(np.float32) / 255.0
    h, _ = arr.shape[:2]
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    top_weight = np.clip(1.5 - 2.0 * y, 0.0, 1.0)

    # Blue / cyan range (OpenCV H is 0..180). Allow a wider grey-cloud pass.
    blue_mask = ((hue >= 90) & (hue <= 140)).astype(np.float32)
    grey_mask = (sat < 0.15).astype(np.float32)
    color_score = np.maximum(blue_mask, grey_mask * 0.8)
    brightness = np.clip((val - 0.3) / 0.7, 0.0, 1.0)

    mask = top_weight * color_score * brightness
    if mask.mean() < _SKY_MIN_HEIGHT_FRAC:
        mask *= 0.0
    return np.clip(mask, 0.0, 1.0)


def replace_sky(
    arr: np.ndarray,
    top_color: tuple[int, int, int] = (80, 140, 220),
    bottom_color: tuple[int, int, int] = (210, 230, 255),
) -> np.ndarray:
    """Replace detected sky pixels with a vertical gradient.

    Simple replacement — not photorealistic sky swap, but useful for
    quickly neutralising a blown-out or overcast sky. Users who want a
    photographic replacement should composite manually.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("replace_sky expects HxWx4 RGBA uint8")
    mask = sky_mask(arr)
    if not mask.any():
        return arr

    h, w = arr.shape[:2]
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    top = np.array(top_color, dtype=np.float32)
    bot = np.array(bottom_color, dtype=np.float32)
    gradient = top[None, None, :] * (1.0 - t) + bot[None, None, :] * t
    gradient = np.broadcast_to(gradient, (h, w, 3)).copy()

    a = mask[..., None]
    orig = arr[..., :3].astype(np.float32)
    blended = orig * (1.0 - a) + gradient * a
    out = arr.copy()
    out[..., :3] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    return out


def remove_background(
    arr: np.ndarray, bg_color: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> np.ndarray:
    """Return an RGBA image where non-foreground pixels are *bg_color*."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("remove_background expects HxWx4 RGBA uint8")
    mask = foreground_mask(arr)
    out = arr.copy()
    bg_r, bg_g, bg_b, bg_a = bg_color
    a = mask[..., None]
    bg = np.array([bg_r, bg_g, bg_b], dtype=np.float32)
    orig = out[..., :3].astype(np.float32)
    out[..., :3] = np.clip(orig * a + bg * (1.0 - a), 0.0, 255.0).astype(np.uint8)
    if bg_a == 0:
        out[..., 3] = (mask * 255.0).astype(np.uint8)
    return out
