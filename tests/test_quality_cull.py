"""Tests for quality-based auto-cull orchestration."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.library import image_index
from Imervue.library.quality_cull import auto_cull_low_quality, score_paths_quality


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


def _sharp(_path):
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(32, 32, 3), dtype=np.uint8)


def _flat(_path):
    return np.full((32, 32, 3), 128, dtype=np.uint8)


def test_score_paths_skips_unreadable():
    def boom(_path):
        raise OSError("nope")

    assert score_paths_quality(["a", "b"], boom) == []


def test_cull_flags_worst_fraction():
    # Two sharp + two flat; the flat pair are the worst and get rejected.
    loaders = {"s1": _sharp, "s2": _sharp, "f1": _flat, "f2": _flat}

    def loader(path):
        return loaders[path](path)

    for path in loaders:
        image_index.upsert_image(path, size=1)
    culled = auto_cull_low_quality(list(loaders), fraction=0.5, loader=loader)
    assert culled == 2
    assert image_index.get_cull_state("f1") == image_index.CULL_REJECT
    assert image_index.get_cull_state("s1") != image_index.CULL_REJECT
