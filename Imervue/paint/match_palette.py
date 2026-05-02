"""Match an image's colours to a target palette.

Per-pixel quantisation: every pixel maps to the palette colour with
the smallest Euclidean RGB distance. Used for two workflows:

* Constraining a paint to a curated palette (manga tone studies,
  pixel-art exports, retro game palettes).
* Reducing colour count for indexed-format export (GIF, indexed PNG)
  before the actual encoder runs.

Pure numpy. Memory-aware: large palettes work but the algorithm
materialises an ``(H × W, N)`` distance matrix per call, so a
2048-colour palette on a 4K image touches ~64 GB. Most palettes
are < 64 entries, well within budget.
"""
from __future__ import annotations

import numpy as np

MAX_PALETTE_SIZE = 4096


def match_palette(
    image: np.ndarray,
    palette: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
) -> np.ndarray:
    """Recolour every pixel to its nearest palette entry.

    ``palette`` is an iterable of RGB triples; alpha is preserved
    from the input. Empty palettes return a copy of the input
    unchanged so callers can wire up "no palette selected" without
    a special case.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    palette_list = list(palette or [])
    if not palette_list:
        return image.copy()
    if len(palette_list) > MAX_PALETTE_SIZE:
        raise ValueError(
            f"palette must have <= {MAX_PALETTE_SIZE} colours, "
            f"got {len(palette_list)}",
        )
    cleaned: list[tuple[int, int, int]] = []
    for entry in palette_list:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            continue
        try:
            rgb = (
                max(0, min(255, int(entry[0]))),
                max(0, min(255, int(entry[1]))),
                max(0, min(255, int(entry[2]))),
            )
            cleaned.append(rgb)
        except (TypeError, ValueError):
            continue
    if not cleaned:
        return image.copy()

    palette_arr = np.array(cleaned, dtype=np.float32)
    rgb = image[..., :3].astype(np.float32)
    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)

    # Per-pixel squared Euclidean distance to every palette entry.
    diff = flat[:, None, :] - palette_arr[None, :, :]
    distances_sq = np.sum(diff * diff, axis=2)
    indices = np.argmin(distances_sq, axis=1)
    quantised = palette_arr[indices].reshape(h, w, 3)

    out = image.copy()
    out[..., :3] = np.clip(quantised, 0.0, 255.0).astype(np.uint8)
    return out


def palette_from_image(
    image: np.ndarray, *, max_colors: int = 16,
) -> list[tuple[int, int, int]]:
    """Extract the most-common ``max_colors`` colours from ``image``.

    A simple frequency-based palette extractor — sorts unique pixels
    by occurrence count and returns the top N. Useful for the
    "extract a palette from this reference image" workflow that
    feeds back into :func:`match_palette`.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    if max_colors <= 0:
        raise ValueError(f"max_colors must be > 0, got {max_colors}")
    rgb = image[..., :3].reshape(-1, 3)
    # Pack each colour into a single uint32 for fast unique-counting.
    packed = (
        rgb[:, 0].astype(np.uint32) * (256 * 256)
        + rgb[:, 1].astype(np.uint32) * 256
        + rgb[:, 2].astype(np.uint32)
    )
    unique, counts = np.unique(packed, return_counts=True)
    order = np.argsort(-counts)[:max_colors]
    chosen = unique[order]
    out: list[tuple[int, int, int]] = []
    for value in chosen:
        v = int(value)
        out.append(((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF))
    return out
