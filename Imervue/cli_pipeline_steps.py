"""Ordered pipeline array transforms and their JSON parameter conversions."""
from __future__ import annotations

import numpy as np
from PIL import Image


_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _step_dehaze(arr, p):
    from Imervue.image.dehaze import dehaze
    return dehaze(arr, float(p.get("strength", 1.0)))


def _step_clahe(arr, p):
    from Imervue.image.clahe import apply_clahe
    return apply_clahe(arr, float(p.get("clip", 2.0)), int(p.get("tiles", 8)))


def _step_dither(arr, p):
    from Imervue.image.dither import ordered_dither
    return ordered_dither(arr, int(p.get("levels", 2)))


def _step_distort(arr, p):
    from Imervue.image.distort import distort
    return distort(arr, str(p.get("mode", "swirl")), float(p.get("strength", 0.5)))


def _step_clarity(arr, p):
    from Imervue.image.local_contrast import apply_clarity
    return apply_clarity(arr, float(p.get("amount", 0.5)))


def _step_texture(arr, p):
    from Imervue.image.local_contrast import apply_texture
    return apply_texture(arr, float(p.get("amount", 0.5)))


def _step_grayscale(arr, _p):
    luma = np.clip(np.rint(arr[..., :3].astype(np.float32) @ _LUMA), 0, 255).astype(np.uint8)
    out = arr.copy()
    out[..., :3] = luma[..., None]
    return out


def _step_invert(arr, _p):
    out = arr.copy()
    out[..., :3] = 255 - out[..., :3]
    return out


def _step_watermark(arr, p):
    from Imervue.image.watermark import WatermarkOptions, apply_watermark
    marked = apply_watermark(Image.fromarray(arr, "RGBA"), WatermarkOptions(
        text=str(p.get("text", "")), corner=str(p.get("corner", "bottom-right")),
        opacity=float(p.get("opacity", 0.6))))
    return np.array(marked)


_PIPELINE_OPS = {
    "dehaze": _step_dehaze, "clahe": _step_clahe, "dither": _step_dither,
    "distort": _step_distort, "clarity": _step_clarity, "texture": _step_texture,
    "grayscale": _step_grayscale, "invert": _step_invert, "watermark": _step_watermark,
}
