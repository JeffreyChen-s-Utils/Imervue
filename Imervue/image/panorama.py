"""
Panorama stitching — wrap OpenCV's high-level ``cv2.Stitcher`` API.

Most hand-held panoramas (landscapes, interiors, city skylines) stitch
cleanly with ``Stitcher_SCANS`` mode, which tolerates parallax better
than ``Stitcher_PANORAMA``. We expose both via :class:`PanoramaOptions`.

The stitcher returns an HxWx3 BGR uint8; we convert to RGBA to match
Imervue's internal format everywhere else.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.panorama")


@dataclass
class PanoramaOptions:
    """Parameters for panorama stitching."""

    mode: str = "panorama"           # "panorama" | "scans"
    crop_black_borders: bool = True  # trim all-black stitched edges


_STATUS_MESSAGES = {
    1: "Not enough images or features — add more overlapping frames.",
    2: "Homography estimation failed — try the 'scans' mode.",
    3: "Camera parameter adjustment failed.",
}


def _load_bgr(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    return rgb[..., ::-1].copy()


def _crop_black(bgr: np.ndarray) -> np.ndarray:
    """Trim rows/cols that are entirely black from the stitched output."""
    gray = bgr.max(axis=2)
    rows = np.where(gray.max(axis=1) > 0)[0]
    cols = np.where(gray.max(axis=0) > 0)[0]
    if len(rows) == 0 or len(cols) == 0:
        return bgr
    r0, r1 = rows[0], rows[-1] + 1
    c0, c1 = cols[0], cols[-1] + 1
    return bgr[r0:r1, c0:c1]


def stitch_panorama(
    paths: list[str | Path], options: PanoramaOptions | None = None,
) -> np.ndarray:
    """Stitch ``paths`` into a panorama, returning HxWx4 RGBA uint8."""
    import cv2

    opts = options or PanoramaOptions()
    if len(paths) < 2:
        raise ValueError("Panorama stitching needs at least two images")
    images = [_load_bgr(p) for p in paths]

    mode_flag = (
        cv2.Stitcher_SCANS if opts.mode == "scans" else cv2.Stitcher_PANORAMA
    )
    stitcher = cv2.Stitcher_create(mode_flag)
    status, stitched = stitcher.stitch(images)
    if status != cv2.STITCHER_OK:
        message = _STATUS_MESSAGES.get(status, f"Stitcher failed with code {status}")
        raise RuntimeError(message)
    if opts.crop_black_borders:
        stitched = _crop_black(stitched)

    rgb = stitched[..., ::-1]
    h, w = rgb.shape[:2]
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = 255
    return rgba
