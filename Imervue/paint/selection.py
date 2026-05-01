"""Selection mask helpers for the paint workspace.

Selections are HxW boolean numpy arrays — ``True`` means "pixel is part
of the active selection". Combination modes ('replace' / 'add' /
'subtract' / 'intersect') mirror MediBang's selection-modifier strip.

The pure-logic primitives here are Qt-free so the selection-tool
dispatchers can be unit-tested without a display server.
"""
from __future__ import annotations

import numpy as np

SELECTION_MODES = ("replace", "add", "subtract", "intersect")
DEFAULT_SELECTION_MODE = "replace"


def combine(
    existing: np.ndarray | None,
    new: np.ndarray,
    mode: str,
) -> np.ndarray:
    """Combine ``new`` into ``existing`` according to ``mode``.

    ``existing`` may be ``None`` (no prior selection) — in that case
    only "replace" and "add" produce a non-empty result; "subtract"
    and "intersect" return an all-False mask of the right shape.
    """
    if mode not in SELECTION_MODES:
        raise ValueError(
            f"unknown selection mode {mode!r}; expected one of {SELECTION_MODES}",
        )
    if new.dtype != np.bool_:
        raise ValueError(f"new selection must be bool, got {new.dtype}")
    if existing is None:
        if mode in ("replace", "add"):
            return new.copy()
        return np.zeros_like(new)
    if existing.shape != new.shape:
        raise ValueError(
            f"selection shapes mismatch: existing {existing.shape}, new {new.shape}",
        )
    if mode == "replace":
        return new.copy()
    if mode == "add":
        return existing | new
    if mode == "subtract":
        return existing & ~new
    return existing & new   # intersect


def rectangle_mask(
    h: int, w: int, x0: int, y0: int, x1: int, y1: int,
) -> np.ndarray:
    """Return a boolean mask covering the given rectangle.

    Coordinates are clamped into ``[0, h)`` / ``[0, w)`` and
    automatically swapped if the user dragged from bottom-right to
    top-left.
    """
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas dimensions must be positive, got {h}x{w}")
    lo_x = max(0, min(w - 1, x0, x1))
    hi_x = max(0, min(w - 1, max(x0, x1)))
    lo_y = max(0, min(h - 1, y0, y1))
    hi_y = max(0, min(h - 1, max(y0, y1)))
    mask = np.zeros((h, w), dtype=np.bool_)
    mask[lo_y:hi_y + 1, lo_x:hi_x + 1] = True
    return mask


def polygon_mask(h: int, w: int, points: list[tuple[float, float]]) -> np.ndarray:
    """Return a boolean mask filled by the polygon defined by ``points``.

    Uses the standard even-odd fill rule. Self-intersecting polygons
    therefore have alternating filled / hole regions, matching Photoshop
    and MediBang's lasso behaviour.
    """
    if h <= 0 or w <= 0:
        raise ValueError(f"canvas dimensions must be positive, got {h}x{w}")
    mask = np.zeros((h, w), dtype=np.bool_)
    if len(points) < 3:
        return mask

    n = len(points)
    for y in range(h):
        crossings: list[float] = []
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                # Linear interpolation: x at scanline y.
                t = (y - y0) / (y1 - y0)
                crossings.append(x0 + t * (x1 - x0))
        crossings.sort()
        for i in range(0, len(crossings), 2):
            if i + 1 >= len(crossings):
                break
            lo = max(0, int(np.ceil(crossings[i])))
            hi = min(w, int(np.floor(crossings[i + 1])) + 1)
            if hi > lo:
                mask[y, lo:hi] = True
    return mask


def magic_wand_mask(
    canvas: np.ndarray,
    seed_x: int,
    seed_y: int,
    *,
    tolerance: int = 32,
    contiguous: bool = True,
) -> np.ndarray:
    """Return a boolean mask of pixels matching the seed within tolerance.

    Internally re-uses the same candidate-mask + 4-connected dilation
    that the fill bucket uses (so the wand and the bucket agree on what
    "the same colour as this pixel" means).
    """
    from Imervue.paint.fill import _contiguous_region

    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"magic_wand_mask expects HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    h, w = canvas.shape[:2]
    sx, sy = int(round(seed_x)), int(round(seed_y))
    if not (0 <= sx < w and 0 <= sy < h):
        return np.zeros((h, w), dtype=np.bool_)

    seed = canvas[sy, sx, :3].astype(np.int16)
    diff = np.abs(canvas[..., :3].astype(np.int16) - seed[None, None, :])
    candidates = diff.max(axis=-1) <= max(0, min(255, int(tolerance)))
    if contiguous:
        return _contiguous_region(candidates, sx, sy)
    return candidates


# ---------------------------------------------------------------------------
# Color-range selection (29d)
# ---------------------------------------------------------------------------

# Hue is circular [0, 360). Saturation / luma are normalised [0, 1].
HUE_TOLERANCE_MIN = 0.0
HUE_TOLERANCE_MAX = 180.0
DEFAULT_HUE_TOLERANCE = 30.0
DEFAULT_SAT_TOLERANCE = 0.3
DEFAULT_LUMA_TOLERANCE = 0.3


def color_range_mask(
    canvas: np.ndarray,
    target: tuple[int, int, int],
    *,
    hue_tolerance: float = DEFAULT_HUE_TOLERANCE,
    sat_tolerance: float = DEFAULT_SAT_TOLERANCE,
    luma_tolerance: float = DEFAULT_LUMA_TOLERANCE,
    alpha_threshold: int = 0,
) -> np.ndarray:
    """Return a boolean mask of pixels in the colour range around ``target``.

    Each pixel is converted to (hue, saturation, luma) and tested
    against ``target``'s components within the supplied tolerances.
    Hue distance is wrap-aware so the band around 0° / 360° works.
    Pixels with alpha at or below ``alpha_threshold`` are excluded so
    transparent areas never get selected (they have meaningless hue).

    The return is HxW bool. Empty / fully-transparent canvases yield
    a fully-False mask of the right shape.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"color_range_mask expects HxWx4 uint8 RGBA, got "
            f"{canvas.shape} {canvas.dtype}",
        )
    if len(target) != 3 or any(not 0 <= int(c) <= 255 for c in target):
        raise ValueError(
            f"target must be a 3-tuple of 0..255 ints, got {target!r}",
        )
    if not HUE_TOLERANCE_MIN <= float(hue_tolerance) <= HUE_TOLERANCE_MAX:
        raise ValueError(
            f"hue_tolerance must be in [{HUE_TOLERANCE_MIN}, "
            f"{HUE_TOLERANCE_MAX}], got {hue_tolerance}",
        )
    if not 0.0 <= float(sat_tolerance) <= 1.0:
        raise ValueError(
            f"sat_tolerance must be in [0, 1], got {sat_tolerance}",
        )
    if not 0.0 <= float(luma_tolerance) <= 1.0:
        raise ValueError(
            f"luma_tolerance must be in [0, 1], got {luma_tolerance}",
        )
    if not 0 <= int(alpha_threshold) <= 255:
        raise ValueError(
            f"alpha_threshold must be in [0, 255], got {alpha_threshold}",
        )

    target_hue, target_sat, target_luma = _rgb_to_hsl_one(target)
    rgb = canvas[..., :3].astype(np.float32) / 255.0
    pixel_hue, pixel_sat, pixel_luma = _rgb_array_to_hsl(rgb)

    # Wrap-aware hue distance.
    hue_diff = np.abs(pixel_hue - target_hue)
    hue_diff = np.minimum(hue_diff, 360.0 - hue_diff)
    sat_diff = np.abs(pixel_sat - target_sat)
    luma_diff = np.abs(pixel_luma - target_luma)

    mask = (
        (hue_diff <= float(hue_tolerance))
        & (sat_diff <= float(sat_tolerance))
        & (luma_diff <= float(luma_tolerance))
    )
    alpha_ok = canvas[..., 3] > int(alpha_threshold)
    return mask & alpha_ok


def _rgb_to_hsl_one(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """RGB-int → (hue°, sat, luma) for a single colour."""
    r = float(rgb[0]) / 255.0
    g = float(rgb[1]) / 255.0
    b = float(rgb[2]) / 255.0
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin
    luma = (cmax + cmin) / 2.0
    if delta == 0:
        hue = 0.0
        sat = 0.0
    else:
        denom = 1.0 - abs(2.0 * luma - 1.0)
        sat = delta / denom if denom > 1e-9 else 0.0
        if cmax == r:
            hue = ((g - b) / delta) % 6.0
        elif cmax == g:
            hue = ((b - r) / delta) + 2.0
        else:
            hue = ((r - g) / delta) + 4.0
        hue *= 60.0
    return (hue, sat, luma)


def _rgb_array_to_hsl(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised RGB-float[0..1] → (hue°, sat, luma) per-pixel."""
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin
    luma = (cmax + cmin) / 2.0
    safe_delta = np.where(delta == 0, 1.0, delta)
    hue = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta != 0)
    mask_g = (cmax == g) & (delta != 0)
    mask_b = (cmax == b) & (delta != 0)
    hue = np.where(mask_r, ((g - b) / safe_delta) % 6.0, hue)
    hue = np.where(mask_g, ((b - r) / safe_delta) + 2.0, hue)
    hue = np.where(mask_b, ((r - g) / safe_delta) + 4.0, hue)
    hue = hue * 60.0
    denom = 1.0 - np.abs(2.0 * luma - 1.0)
    safe_denom = np.where(denom <= 1e-9, 1.0, denom)
    sat = np.where(delta == 0, 0.0, delta / safe_denom)
    return hue, sat, luma
