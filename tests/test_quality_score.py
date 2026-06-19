"""Tests for composite image-quality scoring and culling."""
from __future__ import annotations

import numpy as np

from Imervue.image.quality_score import (
    exposure_score,
    quality_score,
    rank_by_quality,
    select_low_quality,
)


def _checker(h=32, w=32, scale=1):
    rng = np.random.default_rng(0)
    rgb = (rng.integers(0, 256, size=(h, w, 3)) // scale * scale).astype(np.uint8)
    return rgb


def test_exposure_score_penalizes_clipping():
    clean = np.full((16, 16), 128, dtype=np.float64)
    blown = np.full((16, 16), 255, dtype=np.float64)
    assert exposure_score(clean) >= 1.0
    assert exposure_score(blown) < 0.1


def test_quality_in_unit_range():
    score = quality_score(_checker())
    assert 0.0 <= score <= 1.0


def test_sharp_scores_above_blurry():
    sharp = _checker()
    # A flat grey frame has no sharpness and no contrast → lower score.
    blurry = np.full((32, 32, 3), 128, dtype=np.uint8)
    assert quality_score(sharp) > quality_score(blurry)


def test_rank_orders_best_first():
    ranked = rank_by_quality([("a", 0.2), ("b", 0.9), ("c", 0.5)])
    assert [p for p, _ in ranked] == ["b", "c", "a"]


def test_select_low_quality_picks_worst_fraction():
    scores = [("a", 0.9), ("b", 0.8), ("c", 0.2), ("d", 0.1)]
    worst = select_low_quality(scores, fraction=0.5)
    assert set(worst) == {"c", "d"}


def test_select_low_quality_empty():
    assert select_low_quality([], 0.25) == []
