"""Tests for the pure perceptual-hash / near-duplicate grouping module."""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.image.perceptual_hash import (
    ahash,
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


def test_hash_paths_reports_progress_including_skipped(tmp_path):
    good = tmp_path / "g.png"
    _gradient_img().save(str(good))
    calls: list[tuple[int, int]] = []
    hashed = hash_paths(
        [str(good), str(tmp_path / "missing.png")],
        on_progress=lambda done, total: calls.append((done, total)),
    )
    assert len(hashed) == 1               # unreadable still skipped from results
    # ...but progress advances for both and reaches the total.
    assert calls == [(1, 2), (2, 2)]


def test_find_similar_reports_progress(tmp_path):
    _gradient_img().save(str(tmp_path / "a.png"))
    _gradient_img().save(str(tmp_path / "b.png"))
    calls: list[tuple[int, int]] = []
    find_similar(
        [str(tmp_path / "a.png"), str(tmp_path / "b.png")],
        threshold=0,
        on_progress=lambda done, total: calls.append((done, total)),
    )
    assert [done for done, _ in calls] == [1, 2]
    assert all(total == 2 for _, total in calls)


def test_hash_paths_without_callback_accepts_lazy_iterable(tmp_path):
    good = tmp_path / "g.png"
    _gradient_img().save(str(good))
    # Default path must not require a materialised sequence.
    assert len(hash_paths(iter([str(good)]))) == 1


# ---------------------------------------------------------------------------
# Average hash (ahash) + selectable hasher
# ---------------------------------------------------------------------------


def _flat_img(level=128):
    return Image.new("L", (32, 32), level).convert("RGB")


def test_ahash_is_deterministic_and_distinguishing():
    a = ahash(_gradient_img())
    assert ahash(_gradient_img()) == a
    assert ahash(_gradient_img(transpose=True)) != a


def test_ahash_flat_image_sets_all_bits():
    # Every pixel equals the mean, so all 64 bits are set (value >= average).
    assert ahash(_flat_img()) == (1 << 64) - 1


def test_ahash_differs_from_dhash_on_same_image():
    img = _gradient_img()
    assert ahash(img) != dhash(img)


def test_hash_paths_uses_selected_hasher(tmp_path):
    good = tmp_path / "g.png"
    _gradient_img().save(str(good))
    result = hash_paths([str(good)], hasher=ahash)
    assert result[0][1] == ahash(_gradient_img())


def test_find_similar_with_ahash_groups_identical(tmp_path):
    _gradient_img().save(str(tmp_path / "a.png"))
    _gradient_img().save(str(tmp_path / "b.png"))
    _gradient_img(transpose=True).save(str(tmp_path / "c.png"))
    groups = find_similar(
        [str(tmp_path / "a.png"), str(tmp_path / "b.png"), str(tmp_path / "c.png")],
        threshold=0, hasher=ahash)
    assert len(groups) == 1
    assert {p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in groups[0]} == {
        "a.png", "b.png"}


def test_a_tagged_photo_and_its_upright_copy_are_grouped(tmp_path):
    """Hashed as stored, the two were 25 bits apart and never reported as duplicates."""
    from _decode_samples import upright_and_tagged_copies

    from Imervue.image.perceptual_hash import find_similar
    plain, tagged = upright_and_tagged_copies(tmp_path)
    groups = find_similar([plain, tagged])
    assert [sorted(group) for group in groups] == [sorted([plain, tagged])]


def test_an_untagged_image_hashes_as_before(tmp_path):
    from PIL import Image

    from Imervue.image.perceptual_hash import dhash, hash_paths
    path = tmp_path / "a.png"
    Image.effect_noise((40, 30), 50).convert("RGB").save(path)
    with Image.open(path) as img:
        expected = dhash(img)
    assert hash_paths([str(path)]) == [(str(path), expected)]


def test_hash_paths_skips_a_picture_over_the_pixel_limit(tmp_path, monkeypatch):
    """One huge panorama raised DecompressionBombError and ended Find Similar."""
    from PIL import Image

    from Imervue.image.perceptual_hash import hash_paths
    small, huge = tmp_path / "small.png", tmp_path / "huge.png"
    Image.new("RGB", (8, 8)).save(small)
    Image.new("RGB", (64, 64)).save(huge)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    assert [p for p, _ in hash_paths([str(huge), str(small)])] == [str(small)]
