"""
HDR merge — combine bracketed exposures into a single tone-mapped image.

Uses OpenCV's Mertens exposure fusion by default: it does not need the
EXIF exposure times to be correct (unlike the Debevec/Drago path), is
tolerant of small camera movement, and produces natural-looking results
on landscape / architecture brackets without the classic "HDR glow".

The Debevec path is provided as an opt-in for users who have tripod-fixed,
EXIF-tagged brackets and want a linear radiance map they can tonemap with
Reinhard or Drago.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.hdr_merge")


@dataclass
class HdrOptions:
    """Parameters controlling HDR merge behaviour."""

    method: str = "mertens"          # "mertens" (exposure fusion) | "debevec"
    align: bool = True               # run AlignMTB before merging
    gamma: float = 1.0               # post-merge gamma (Mertens only)
    tonemap_gamma: float = 1.0       # Reinhard gamma (Debevec only)
    tonemap_intensity: float = 0.0   # Reinhard intensity (Debevec only)
    tonemap_light_adapt: float = 1.0 # Reinhard light adaptation (Debevec only)


def _load_bgr(path: str | Path) -> np.ndarray:
    """Return an HxWx3 uint8 BGR image — cv2 format."""
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    return rgb[..., ::-1].copy()


def _align(images: list[np.ndarray]):
    import cv2
    aligner = cv2.createAlignMTB()
    aligner.process(images, images)
    return images


def _mertens(images: list[np.ndarray], gamma: float) -> np.ndarray:
    import cv2
    merge = cv2.createMergeMertens()
    fused = merge.process(images)
    fused = np.clip(fused, 0.0, 1.0)
    if abs(gamma - 1.0) > 1e-6:
        fused = np.power(fused, 1.0 / max(gamma, 1e-3))
    bgr = (fused * 255.0 + 0.5).astype(np.uint8)
    return bgr


def _debevec(
    images: list[np.ndarray], exposure_times: list[float], opts: HdrOptions,
) -> np.ndarray:
    import cv2
    times = np.asarray(exposure_times, dtype=np.float32)
    calib = cv2.createCalibrateDebevec()
    response = calib.process(images, times)
    merger = cv2.createMergeDebevec()
    hdr = merger.process(images, times, response)
    tonemap = cv2.createTonemapReinhard(
        gamma=max(0.1, opts.tonemap_gamma),
        intensity=opts.tonemap_intensity,
        light_adapt=opts.tonemap_light_adapt,
        color_adapt=0.0,
    )
    ldr = tonemap.process(hdr)
    ldr = np.clip(ldr, 0.0, 1.0)
    return (ldr * 255.0 + 0.5).astype(np.uint8)


def merge_hdr(
    paths: list[str | Path],
    options: HdrOptions | None = None,
    exposure_times: list[float] | None = None,
) -> np.ndarray:
    """Merge bracketed exposures into a single RGBA uint8 image.

    ``exposure_times`` is only used when ``options.method == "debevec"``; for
    ``"mertens"`` it is ignored. Returns an HxWx4 RGBA uint8 array.
    """
    opts = options or HdrOptions()
    if len(paths) < 2:
        raise ValueError("HDR merge needs at least two images")
    images = [_load_bgr(p) for p in paths]
    first_shape = images[0].shape[:2]
    for i, img in enumerate(images):
        if img.shape[:2] != first_shape:
            raise ValueError(
                f"image {i} shape {img.shape[:2]} != first shape {first_shape}"
            )
    if opts.align:
        images = _align(images)
    if opts.method == "debevec":
        if not exposure_times or len(exposure_times) != len(paths):
            raise ValueError("Debevec HDR requires one exposure time per image")
        bgr = _debevec(images, exposure_times, opts)
    else:
        bgr = _mertens(images, opts.gamma)
    rgb = bgr[..., ::-1]
    h, w = rgb.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = 255
    return rgba
