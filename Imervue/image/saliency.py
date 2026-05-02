"""Heuristic saliency + rule-of-thirds crop suggester.

Pure numpy — no ML model. Computes a saliency field from local edge
energy (Sobel magnitude on luminance), then proposes crop frames whose
centre-of-mass lands on a rule-of-thirds intersection. Three aspect
presets ship out of the box: free (preserve), 4:5 (Instagram portrait),
16:9 (banner). Each is scored by the saliency mass it captures.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ASPECT_PRESETS: dict[str, float | None] = {
    "free": None,
    "1:1": 1.0,
    "4:5": 4.0 / 5.0,
    "3:2": 3.0 / 2.0,
    "16:9": 16.0 / 9.0,
}

# Number of candidate crops we score per preset. Higher = better but
# slower; 24 covers all four rule-of-thirds anchor points × six sizes.
_CANDIDATES_PER_PRESET = 24
_MIN_CROP_FRACTION = 0.4   # crops must keep at least this much of the long edge


@dataclass(frozen=True)
class CropSuggestion:
    """A proposed crop rectangle in image-space pixels (x, y, w, h)."""

    x: int
    y: int
    w: int
    h: int
    score: float


def saliency_field(arr: np.ndarray) -> np.ndarray:
    """Return a HxW float32 saliency field in ``[0, 1]``.

    Uses Sobel-magnitude on luminance + a centre-bias term so subjects
    in the middle of the frame outweigh edge clutter.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"saliency_field expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    ).astype(np.float32)
    gx = _sobel_x(luma)
    gy = _sobel_y(luma)
    edge_mag = np.sqrt(gx * gx + gy * gy)

    h, w = luma.shape
    if edge_mag.max() > 0:
        edge_mag = edge_mag / edge_mag.max()
    centre_bias = _centre_bias_field(h, w)
    field = 0.7 * edge_mag + 0.3 * centre_bias
    return np.clip(field, 0.0, 1.0)


def suggest_crops(
    arr: np.ndarray,
    presets: tuple[str, ...] = ("free", "1:1", "4:5", "16:9"),
) -> dict[str, CropSuggestion]:
    """Return one ``CropSuggestion`` per preset name in ``presets``."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"suggest_crops expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    field = saliency_field(arr)
    h, w = arr.shape[:2]
    results: dict[str, CropSuggestion] = {}
    for preset in presets:
        ratio = ASPECT_PRESETS.get(preset)
        results[preset] = _best_crop_for_aspect(field, h, w, ratio)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sobel_x(plane: np.ndarray) -> np.ndarray:
    """Horizontal Sobel without OpenCV. Returns same shape as input."""
    padded = np.pad(plane, 1, mode="edge")
    return (
        -padded[:-2, :-2] - 2 * padded[1:-1, :-2] - padded[2:, :-2]
        + padded[:-2, 2:] + 2 * padded[1:-1, 2:] + padded[2:, 2:]
    )


def _sobel_y(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    return (
        -padded[:-2, :-2] - 2 * padded[:-2, 1:-1] - padded[:-2, 2:]
        + padded[2:, :-2] + 2 * padded[2:, 1:-1] + padded[2:, 2:]
    )


def _centre_bias_field(h: int, w: int) -> np.ndarray:
    """A radial Gaussian centred on the image, normalised to ``[0, 1]``."""
    yy, xx = np.indices((h, w), dtype=np.float32)
    cx = (w - 1) * 0.5
    cy = (h - 1) * 0.5
    sigma = 0.5 * min(h, w)
    dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2
    return np.exp(-dist_sq / (2.0 * sigma * sigma))


def _best_crop_for_aspect(
    field: np.ndarray, h: int, w: int, aspect: float | None,
) -> CropSuggestion:
    """Search ``_CANDIDATES_PER_PRESET`` rectangles and return the best-scored."""
    if aspect is None:
        # "free" preset returns the full image
        return CropSuggestion(0, 0, w, h, float(field.sum()))

    # Build candidate sizes covering 60-95% of the image's long dimension.
    candidates = list(_iter_candidates(h, w, aspect))
    if not candidates:
        return CropSuggestion(0, 0, w, h, float(field.sum()))

    best = None
    for x, y, cw, ch in candidates:
        score = float(field[y:y + ch, x:x + cw].sum())
        if best is None or score > best.score:
            best = CropSuggestion(x=x, y=y, w=cw, h=ch, score=score)
    return best  # type: ignore[return-value]


def _iter_candidates(h: int, w: int, aspect: float):
    """Yield (x, y, cw, ch) candidate rects of the given aspect ratio."""
    sizes = _candidate_sizes(h, w, aspect)
    if not sizes:
        return
    # Anchor each size at the four rule-of-thirds intersections + image centre.
    rule_of_thirds = (1.0 / 3.0, 2.0 / 3.0)
    for cw, ch in sizes[: max(1, _CANDIDATES_PER_PRESET // 4)]:
        for tx in rule_of_thirds:
            for ty in rule_of_thirds:
                cx = int(round(tx * w))
                cy = int(round(ty * h))
                x = max(0, min(w - cw, cx - cw // 2))
                y = max(0, min(h - ch, cy - ch // 2))
                yield x, y, cw, ch


def _candidate_sizes(h: int, w: int, aspect: float) -> list[tuple[int, int]]:
    """Return descending-area rects of ``aspect`` that fit inside ``(w, h)``."""
    sizes: list[tuple[int, int]] = []
    long_edge = max(h, w)
    fractions = [0.95, 0.85, 0.75, 0.65, 0.55, _MIN_CROP_FRACTION]
    for frac in fractions:
        target_long = int(round(long_edge * frac))
        if aspect >= 1.0:
            cw = target_long
            ch = int(round(cw / aspect))
        else:
            ch = target_long
            cw = int(round(ch * aspect))
        if cw <= w and ch <= h and cw > 0 and ch > 0:
            sizes.append((cw, ch))
    return sizes
