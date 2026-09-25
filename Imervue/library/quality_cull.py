"""Auto-cull the weakest frames by composite technical quality.

Scores each image with the multi-factor :func:`quality_score` (sharpness +
exposure + contrast) and marks the worst-scoring fraction as cull ``reject``.
The scoring loop is pure when given a loader, so it is unit-tested with
synthetic arrays; the default loader downscales to RGB for comparable scores.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.quality_score import quality_score, select_low_quality

_MAX_SIDE = 512
DEFAULT_FRACTION = 0.25


def score_paths_quality(
    paths: Iterable[str], loader: Callable[[str], np.ndarray],
) -> list[tuple[str, float]]:
    """Return ``(path, quality)`` for each path; unreadable paths are skipped."""
    scores: list[tuple[str, float]] = []
    for path in paths:
        try:
            arr = loader(path)
        except IMAGE_READ_ERRORS:   # a huge file (DecompressionBombError) must not end the batch
            continue
        scores.append((path, quality_score(arr)))
    return scores


def _load_for_scoring(path: str) -> np.ndarray:
    """*path* as the viewer decodes it, at most 512 px on the long side.

    Upright, a camera RAW through its embedded preview, HEIC / JPEG XL read:
    ``Image.open`` scored a RAW by its tiny TIFF thumbnail, or not at all.
    """
    from Imervue.gpu_image_view.images.image_loader import decode_image
    rgb = decode_image(path, max_edge=_MAX_SIDE).convert("RGB")
    return np.asarray(rgb, dtype=np.uint8)


def auto_cull_low_quality(
    paths: Iterable[str],
    fraction: float = DEFAULT_FRACTION,
    *,
    loader: Callable[[str], np.ndarray] | None = None,
) -> int:
    """Flag the worst *fraction* of images as cull reject. Returns the count."""
    from Imervue.library import image_index
    scores = score_paths_quality(paths, loader or _load_for_scoring)
    low = select_low_quality(scores, fraction)
    for path in low:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    return len(low)
