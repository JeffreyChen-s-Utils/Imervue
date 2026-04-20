"""Crop, straighten, and perspective correction.

Straighten rotates by an arbitrary angle and crops to the largest
axis-aligned rectangle that remains fully inside the rotated content —
no black corners, no transparent padding.

Perspective correction takes four source corner points (in image
coordinates) and warps them to a rectangle of the requested output size,
handy for fixing keystone on building photos or un-skewing scanned pages.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.geometry")

_MIN_DIM = 4


@dataclass(frozen=True)
class CropRect:
    """Normalised crop rectangle in fractions of the image (0..1)."""

    x: float
    y: float
    w: float
    h: float

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        px = max(0, int(round(self.x * width)))
        py = max(0, int(round(self.y * height)))
        pw = max(_MIN_DIM, int(round(self.w * width)))
        ph = max(_MIN_DIM, int(round(self.h * height)))
        pw = min(pw, width - px)
        ph = min(ph, height - py)
        return px, py, pw, ph


def apply_crop(arr: np.ndarray, rect: CropRect) -> np.ndarray:
    """Return a cropped view of *arr* (HxWxC) by the normalised *rect*."""
    if arr.ndim < 2:
        raise ValueError("apply_crop expects at least a 2-D array")
    h, w = arr.shape[:2]
    x, y, cw, ch = rect.to_pixels(w, h)
    return np.ascontiguousarray(arr[y:y + ch, x:x + cw])


def _largest_inner_rect(w: int, h: int, angle_deg: float) -> tuple[int, int, int, int]:
    """Largest axis-aligned rect that fits inside w×h rotated by *angle_deg*.

    Returns (x, y, rect_w, rect_h) in the rotated-canvas coordinate frame.
    Uses the closed-form solution from
    https://stackoverflow.com/a/16778797 (Suffield, 2013).
    """
    if w <= 0 or h <= 0:
        return 0, 0, 0, 0
    angle = abs(math.radians(angle_deg)) % math.pi
    if angle > math.pi / 2:
        angle = math.pi - angle
    long_side, short_side = (w, h) if w >= h else (h, w)
    sin_a, cos_a = math.sin(angle), math.cos(angle)
    if short_side <= 2.0 * sin_a * cos_a * long_side or abs(sin_a - cos_a) < 1e-10:
        x_scale = 0.5 * short_side
        rw, rh = (x_scale / sin_a, x_scale / cos_a) if w >= h else (x_scale / cos_a, x_scale / sin_a)
    else:
        cos2a = cos_a * cos_a - sin_a * sin_a
        rw = (w * cos_a - h * sin_a) / cos2a
        rh = (h * cos_a - w * sin_a) / cos2a
    rw, rh = int(max(_MIN_DIM, rw)), int(max(_MIN_DIM, rh))
    # Center inside the rotated bounding box
    rot_w = int(abs(w * cos_a) + abs(h * sin_a))
    rot_h = int(abs(w * sin_a) + abs(h * cos_a))
    x = max(0, (rot_w - rw) // 2)
    y = max(0, (rot_h - rh) // 2)
    return x, y, rw, rh


def straighten(
    arr: np.ndarray, angle_deg: float, crop_to_content: bool = True,
) -> np.ndarray:
    """Rotate *arr* by *angle_deg* (CCW) and crop to the largest inner rect."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("straighten expects HxWx4 RGBA uint8")
    if abs(angle_deg) < 1e-4:
        return arr

    import cv2
    h, w = arr.shape[:2]
    bgr = arr[..., [2, 1, 0, 3]].copy()
    rot_m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    abs_cos, abs_sin = abs(rot_m[0, 0]), abs(rot_m[0, 1])
    new_w = int(h * abs_sin + w * abs_cos)
    new_h = int(h * abs_cos + w * abs_sin)
    rot_m[0, 2] += (new_w / 2.0) - w / 2.0
    rot_m[1, 2] += (new_h / 2.0) - h / 2.0
    rotated = cv2.warpAffine(
        bgr, rot_m, (new_w, new_h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    if crop_to_content:
        x, y, rw, rh = _largest_inner_rect(w, h, angle_deg)
        rotated = rotated[y:y + rh, x:x + rw]
    return np.ascontiguousarray(rotated[..., [2, 1, 0, 3]])


def correct_perspective(
    arr: np.ndarray,
    src_points: list[tuple[float, float]],
    output_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Warp a 4-point quad in *arr* to a rectangle of *output_size* (w, h)."""
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("correct_perspective expects HxWx4 RGBA uint8")
    if len(src_points) != 4:
        raise ValueError("correct_perspective needs exactly 4 source points")

    import cv2
    src = np.asarray(src_points, dtype=np.float32)
    if output_size is None:
        top_w = np.linalg.norm(src[1] - src[0])
        bot_w = np.linalg.norm(src[2] - src[3])
        left_h = np.linalg.norm(src[3] - src[0])
        right_h = np.linalg.norm(src[2] - src[1])
        out_w = int(max(top_w, bot_w))
        out_h = int(max(left_h, right_h))
    else:
        out_w, out_h = int(output_size[0]), int(output_size[1])
    out_w = max(_MIN_DIM, out_w)
    out_h = max(_MIN_DIM, out_h)
    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    bgr = arr[..., [2, 1, 0, 3]].copy()
    mtx = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(
        bgr, mtx, (out_w, out_h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return np.ascontiguousarray(warped[..., [2, 1, 0, 3]])
