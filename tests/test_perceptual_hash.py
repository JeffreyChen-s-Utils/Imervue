"""Tests for the pure perceptual-hash / near-duplicate grouping module."""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.image.perceptual_hash import (
    dhash,
    find_similar,
    group_similar,
    hamming_distance,
    hash_paths,
)


def _gradient_img(transpose=False):
    ramp = np.tile(np.linspace(0, 255, 32, dtype=np.uint8), (32, 1))
    if transpose:
        ramp = ramp.T
    return Image.fromarray(ramp, "L").convert("RGB")


def test_dhash_is_deterministic_and_distinguishing():
    a = dhash(_gradient_img())
    assert dhash(_gradient_img()) == a            # deterministic
    assert dhash(_gradient_img(transpose=True)) != a  # different content differs


def test_hamming_distance():
    assert hamming_distance(0b1010, 0b1010) == 0
    assert hamming_distance(0b1010, 0b1011) == 1
    assert hamming_distance(0, 0b1111) == 4


def test_group_similar_clusters_close_hashes():
    hashed = [("a", 0b0000), ("b", 0b0001), ("c", 0xFFFF)]
    groups = group_similar(hashed, threshold=1)
    assert groups == [["a", "b"]]


def test_group_similar_threshold_zero_needs_identical():
    hashed = [("a", 5), ("b", 5), ("c", 7)]
    assert group_similar(hashed, threshold=0) == [["a", "b"]]


def test_hash_paths_skips_unreadable(tmp_path):
    good = tmp_path / "g.png"
    _gradient_img().save(str(good))
    hashed = hash_paths([str(good), str(tmp_path / "missing.png")])
    assert len(hashed) == 1 and hashed[0][0].endswith("g.png")


def test_find_similar_groups_duplicates(tmp_path):
    _gradient_img().save(str(tmp_path / "a.png"))
    _gradient_img().save(str(tmp_path / "b.png"))      # identical content
    _gradient_img(transpose=True).save(str(tmp_path / "c.png"))  # different
    groups = find_similar(
        [str(tmp_path / "a.png"), str(tmp_path / "b.png"), str(tmp_path / "c.png")],
        threshold=0)
    assert len(groups) == 1
    assert {p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in groups[0]} == {"a.png", "b.png"}
