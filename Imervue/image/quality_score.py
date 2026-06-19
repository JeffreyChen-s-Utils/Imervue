"""Technical image-quality scoring for culling.

A composite, model-free "keeper" score combining the three technical factors a
photographer checks first: sharpness (variance of Laplacian), exposure (penalty
for blown / crushed clipping) and contrast (luma spread). Higher is better.
Unlike the blur-only auto-cull, this ranks a shoot by overall technical quality
so the weakest frames can be flagged in one pass.

Pure NumPy, reusing the sharpness metric from :mod:`Imervue.image.sharpness`.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from Imervue.image.sharpness import laplacian_variance, to_luma

_CLIP_LOW = 4
_CLIP_HIGH = 251
_SHARP_REF = 300.0   # Laplacian variance that already counts as "tack sharp"
_CONTRAST_REF = 64.0  # luma std that counts as full, healthy contrast
_W_SHARP = 0.5
_W_EXPOSURE = 0.3
_W_CONTRAST = 0.2


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def exposure_score(luma: np.ndarray) -> float:
    """1.0 when nothing is clipped, falling toward 0 as more pixels blow/crush."""
    if luma.size == 0:
        return 0.0
    clipped = np.count_nonzero((luma <= _CLIP_LOW) | (luma >= _CLIP_HIGH))
    return _clip01(1.0 - clipped / luma.size)


def quality_score(arr: np.ndarray) -> float:
    """Composite technical-quality score in ``[0, 1]`` (higher is better)."""
    luma = to_luma(arr)
    sharp = _clip01(laplacian_variance(luma) / _SHARP_REF)
    exposure = exposure_score(luma)
    contrast = _clip01(float(luma.std()) / _CONTRAST_REF)
    return _W_SHARP * sharp + _W_EXPOSURE * exposure + _W_CONTRAST * contrast


def rank_by_quality(scores_by_path: Iterable[tuple[str, float]]) -> list[tuple[str, float]]:
    """Return ``(path, score)`` pairs sorted best-first."""
    return sorted(scores_by_path, key=lambda item: item[1], reverse=True)


def select_low_quality(
    scores_by_path: Iterable[tuple[str, float]], fraction: float = 0.25,
) -> list[str]:
    """Return the worst-scoring *fraction* of paths (the cull candidates)."""
    ranked = rank_by_quality(scores_by_path)
    if not ranked:
        return []
    cut = max(1, round(len(ranked) * _clip01(fraction)))
    return [path for path, _score in ranked[-cut:]]
