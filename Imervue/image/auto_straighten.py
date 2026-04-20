"""Auto-straighten — detect dominant horizon / vertical lines via Hough.

Strategy:

1. Edge map (Canny).
2. Probabilistic Hough line detection.
3. Split lines into near-horizontal and near-vertical buckets.
4. Return the median deviation angle from the larger bucket.

For horizons, a deviation of +2° means the image is tilted 2° clockwise
and should be rotated -2° to level. The sign convention matches
:func:`Imervue.image.geometry.straighten` (positive angle = CCW rotation).
"""
from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger("Imervue.auto_straighten")

_MAX_ANGLE_DEG = 15.0
_HORIZ_THRESHOLD_DEG = 45.0   # lines within ±45° of horizontal go to horiz bucket
_MIN_LINES = 3


def _line_angle_deg(x1: int, y1: int, x2: int, y2: int) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def _normalise_angle(angle: float) -> float:
    """Normalise an angle to (-90, 90]."""
    while angle > 90.0:
        angle -= 180.0
    while angle <= -90.0:
        angle += 180.0
    return angle


def _bucket_line_angles(
    lines: np.ndarray,
) -> tuple[list[float], list[float]]:
    horiz_devs: list[float] = []
    vert_devs: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = _normalise_angle(_line_angle_deg(x1, y1, x2, y2))
        if abs(angle) <= _HORIZ_THRESHOLD_DEG:
            horiz_devs.append(angle)
        else:
            vert_devs.append(angle - 90.0 if angle > 0 else angle + 90.0)
    return horiz_devs, vert_devs


def _detect_lines(arr: np.ndarray):
    try:
        import cv2
    except ImportError:
        return None
    gray = cv2.cvtColor(arr[..., :3], cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 180, apertureSize=3)
    min_len = max(30, min(arr.shape[:2]) // 10)
    return cv2.HoughLinesP(
        edges, rho=1.0, theta=np.pi / 360.0, threshold=80,
        minLineLength=min_len, maxLineGap=10,
    )


def detect_horizon_angle(arr: np.ndarray) -> float:
    """Return the rotation angle (degrees) that would level the image.

    Positive result → image is tilted CW; rotate by this amount to correct.
    Returns 0.0 when no dominant line is found or OpenCV is unavailable.
    """
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("detect_horizon_angle expects HxWx4 RGBA uint8")

    lines = _detect_lines(arr)
    if lines is None or len(lines) < _MIN_LINES:
        return 0.0

    horiz_devs, vert_devs = _bucket_line_angles(lines)
    # Prefer the larger bucket so portraits of buildings pick verticals,
    # landscape horizons pick horizontals.
    bucket = horiz_devs if len(horiz_devs) >= len(vert_devs) else vert_devs
    if len(bucket) < _MIN_LINES:
        return 0.0
    angle = float(np.median(bucket))
    if abs(angle) > _MAX_ANGLE_DEG:
        return 0.0
    return angle
