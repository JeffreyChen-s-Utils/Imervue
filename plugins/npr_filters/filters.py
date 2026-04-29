"""Non-photorealistic rendering filters.

Wraps OpenCV's stylization functions to produce four art-style looks
from a single RGBA frame: pencil sketch, oil painting, watercolour, and
line art. All functions accept and return ``HxWx4 uint8`` arrays so the
plugin output drops cleanly into the existing save pipeline.

OpenCV is the only heavy dependency. ``pencilSketch`` and
``stylization`` ship in stock opencv-python (no contrib needed). Oil
painting falls back to a bilateral + posterise simulation since
``cv2.xphoto.oilPainting`` lives in opencv-contrib only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

STYLES = ("pencil_sketch", "oil_painting", "watercolor", "line_art")

INTENSITY_MIN = 0.0
INTENSITY_MAX = 1.0
SIGMA_S_MIN = 10
SIGMA_S_MAX = 200
SIGMA_R_MIN = 5
SIGMA_R_MAX = 100
OIL_LEVELS_MIN = 4
OIL_LEVELS_MAX = 32
LINE_THRESHOLD_MIN = 20
LINE_THRESHOLD_MAX = 200

_DEFAULT_SIGMA_S = 60
_DEFAULT_SIGMA_R = 45
_DEFAULT_OIL_LEVELS = 8
_DEFAULT_LINE_THRESHOLD = 80


@dataclass(frozen=True)
class NPRFilterOptions:
    """Tuning knobs for :func:`apply_npr_filter`."""

    style: str = "pencil_sketch"
    intensity: float = 1.0          # blend with original
    sigma_s: int = _DEFAULT_SIGMA_S       # spatial scale (stylization / sketch)
    sigma_r: int = _DEFAULT_SIGMA_R       # range / detail (stylization / sketch)
    oil_levels: int = _DEFAULT_OIL_LEVELS    # quantisation levels (oil_painting)
    line_threshold: int = _DEFAULT_LINE_THRESHOLD  # Canny high threshold (line_art)


def apply_npr_filter(arr: np.ndarray, options: NPRFilterOptions | None = None) -> np.ndarray:
    """Run the configured style filter and blend with the original.

    Returns ``HxWx4 uint8`` regardless of the input alpha channel — the
    alpha is preserved unchanged.
    """
    _check_input(arr)
    options = options or NPRFilterOptions()
    if options.style not in STYLES:
        raise ValueError(f"unknown style {options.style!r}; expected one of {STYLES}")

    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, float(options.intensity)))
    if intensity <= 0.0:
        return arr.copy()

    rgb = arr[..., :3]
    alpha = arr[..., 3:4]

    stylised = _dispatch(rgb, options)
    blended = _blend(rgb, stylised, intensity)
    return np.concatenate([blended, alpha], axis=-1)


def pencil_sketch(rgb: np.ndarray, sigma_s: int, sigma_r: int) -> np.ndarray:
    """OpenCV's pencil sketch filter — colour pencil variant."""
    import cv2
    bgr = rgb[..., ::-1].copy()
    sigma_s_clamped = _clamp(sigma_s, SIGMA_S_MIN, SIGMA_S_MAX)
    sigma_r_clamped = _clamp(sigma_r, SIGMA_R_MIN, SIGMA_R_MAX) / 100.0
    _gray, color = cv2.pencilSketch(
        bgr, sigma_s=float(sigma_s_clamped),
        sigma_r=float(sigma_r_clamped), shade_factor=0.05,
    )
    return color[..., ::-1]


def oil_painting(rgb: np.ndarray, levels: int) -> np.ndarray:
    """Oil-painting effect using bilateral smoothing + level posterisation.

    Approximates ``cv2.xphoto.oilPainting`` (which requires
    opencv-contrib): edge-preserving smoothing flattens the canvas, then
    quantising to ``levels`` per channel produces the blocky "brush"
    look that oil paintings have under low light.
    """
    import cv2
    bgr = rgb[..., ::-1].copy()
    smoothed = cv2.bilateralFilter(bgr, d=9, sigmaColor=75, sigmaSpace=75)
    levels_clamped = _clamp(levels, OIL_LEVELS_MIN, OIL_LEVELS_MAX)
    step = 256 // levels_clamped
    quantised = (smoothed // step) * step + step // 2
    quantised = np.clip(quantised, 0, 255).astype(np.uint8)
    return quantised[..., ::-1]


def watercolor(rgb: np.ndarray, sigma_s: int, sigma_r: int) -> np.ndarray:
    """OpenCV's stylization filter; reads as watercolour-on-paper."""
    import cv2
    bgr = rgb[..., ::-1].copy()
    sigma_s_clamped = _clamp(sigma_s, SIGMA_S_MIN, SIGMA_S_MAX)
    sigma_r_clamped = _clamp(sigma_r, SIGMA_R_MIN, SIGMA_R_MAX) / 100.0
    out = cv2.stylization(
        bgr, sigma_s=float(sigma_s_clamped),
        sigma_r=float(sigma_r_clamped),
    )
    return out[..., ::-1]


def line_art(rgb: np.ndarray, threshold: int) -> np.ndarray:
    """Inverted Canny edges on a white background — pen / line-art look."""
    import cv2
    gray = cv2.cvtColor(rgb[..., ::-1], cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0.0)
    threshold_clamped = _clamp(threshold, LINE_THRESHOLD_MIN, LINE_THRESHOLD_MAX)
    edges = cv2.Canny(blurred, threshold1=threshold_clamped // 2,
                      threshold2=threshold_clamped)
    inverted = 255 - edges
    return np.stack([inverted, inverted, inverted], axis=-1)


def _dispatch(rgb: np.ndarray, options: NPRFilterOptions) -> np.ndarray:
    style = options.style
    if style == "pencil_sketch":
        return pencil_sketch(rgb, options.sigma_s, options.sigma_r)
    if style == "oil_painting":
        return oil_painting(rgb, options.oil_levels)
    if style == "watercolor":
        return watercolor(rgb, options.sigma_s, options.sigma_r)
    if style == "line_art":
        return line_art(rgb, options.line_threshold)
    raise ValueError(f"unknown style {style!r}")


def _blend(original: np.ndarray, stylised: np.ndarray, intensity: float) -> np.ndarray:
    if intensity >= 1.0 - 1e-6:
        return stylised
    a = original.astype(np.float32)
    b = stylised.astype(np.float32)
    out = a * (1.0 - intensity) + b * intensity
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def _check_input(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"NPR filters expect HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))
