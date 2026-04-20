"""Soft proofing — simulate an output ICC profile and flag out-of-gamut pixels.

Uses Pillow's ``ImageCms`` when a profile file is supplied. Returns a
simulated preview plus a boolean mask of pixels that clipped during the
RGB→profile→RGB round-trip (i.e. out-of-gamut).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.soft_proof")

_DEFAULT_INTENT = 0   # perceptual
_GAMUT_THRESHOLD = 2  # per-channel 0..255 diff considered clipping


def simulate_profile(
    arr: np.ndarray, profile_path: str | Path,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (simulated_rgba, out_of_gamut_mask).

    Returns ``None`` if ImageCms or the profile are unavailable. The mask is
    a HxW bool array — True means the pixel clipped when converted to the
    destination gamut.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("simulate_profile expects HxWx4 RGBA uint8")

    try:
        from PIL import Image, ImageCms
    except ImportError:
        logger.info("Pillow ImageCms unavailable — soft proofing disabled")
        return None
    p = Path(profile_path)
    if not p.is_file():
        logger.info("Profile not found: %s", p)
        return None

    try:
        src_profile = ImageCms.createProfile("sRGB")
        dst_profile = ImageCms.getOpenProfile(str(p))
        fwd = ImageCms.buildTransform(
            src_profile, dst_profile, "RGB", "RGB", renderingIntent=_DEFAULT_INTENT,
        )
        back = ImageCms.buildTransform(
            dst_profile, src_profile, "RGB", "RGB", renderingIntent=_DEFAULT_INTENT,
        )
    except (ImageCms.PyCMSError, OSError) as err:
        logger.warning("Failed to build CMS transforms: %s", err)
        return None

    rgb_img = Image.fromarray(arr[..., :3], mode="RGB")
    proofed_rgb = ImageCms.applyTransform(rgb_img, fwd)
    back_rgb = ImageCms.applyTransform(proofed_rgb, back)

    back_arr = np.array(back_rgb)
    diff = np.abs(back_arr.astype(np.int16) - arr[..., :3].astype(np.int16))
    oog = (diff.max(axis=-1) > _GAMUT_THRESHOLD)

    out = arr.copy()
    out[..., :3] = back_arr
    return out, oog
