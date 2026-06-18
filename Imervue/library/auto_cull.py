"""Auto-cull blurry images by sharpness score.

Scores each image with the Laplacian-variance blur metric and marks the ones
below a threshold as cull ``reject`` (the existing pick/reject workflow). The
scoring loop is pure when given a loader, so it is unit-tested with synthetic
arrays; the default loader downscales to grayscale for comparable scores.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np

from Imervue.image.sharpness import (
    DEFAULT_BLUR_THRESHOLD,
    select_blurry,
    sharpness_score,
)

_MAX_SIDE = 512


def score_paths(
    paths: Iterable[str], loader: Callable[[str], np.ndarray],
) -> list[tuple[str, float]]:
    """Return ``(path, sharpness)`` for each path; unreadable paths are skipped."""
    scores: list[tuple[str, float]] = []
    for path in paths:
        try:
            arr = loader(path)
        except (OSError, ValueError):
            continue
        scores.append((path, sharpness_score(arr)))
    return scores


def _load_for_scoring(path: str) -> np.ndarray:
    from PIL import Image
    with Image.open(path) as src:
        gray = src.convert("L")
        gray.thumbnail((_MAX_SIDE, _MAX_SIDE))
        return np.asarray(gray, dtype=np.float64)


def auto_cull_blurry(
    paths: Iterable[str],
    threshold: float = DEFAULT_BLUR_THRESHOLD,
    *,
    loader: Callable[[str], np.ndarray] | None = None,
) -> int:
    """Flag images below *threshold* sharpness as cull reject. Returns the count."""
    from Imervue.library import image_index
    scores = score_paths(paths, loader or _load_for_scoring)
    blurry = select_blurry(scores, threshold)
    for path in blurry:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    return len(blurry)
