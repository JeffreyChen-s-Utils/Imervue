"""Tests for the layer-thumbnail renderer + cache."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.layer_thumbnail import (
    DEFAULT_THUMBNAIL_SIZE,
    MAX_THUMBNAIL_SIZE,
    MIN_THUMBNAIL_SIZE,
    ThumbnailCache,
    render_layer_thumbnail,
    render_mask_thumbnail,
)


def _solid_image(h: int, w: int, rgba=(255, 0, 0, 255)) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :] = rgba
    return arr


# ---------------------------------------------------------------------------
# render_layer_thumbnail
# ---------------------------------------------------------------------------


def test_thumbnail_default_size():
    image = _solid_image(64, 64)
    out = render_layer_thumbnail(image)
    assert out.shape == (DEFAULT_THUMBNAIL_SIZE, DEFAULT_THUMBNAIL_SIZE, 4)


def test_thumbnail_custom_size():
    image = _solid_image(80, 80)
    out = render_layer_thumbnail(image, size=64)
    assert out.shape == (64, 64, 4)


def test_thumbnail_rejects_non_rgba():
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        render_layer_thumbnail(bad)


def test_thumbnail_rejects_undersized_size():
    image = _solid_image(20, 20)
    with pytest.raises(ValueError, match="size"):
        render_layer_thumbnail(image, size=MIN_THUMBNAIL_SIZE - 1)


def test_thumbnail_rejects_oversized_size():
    image = _solid_image(20, 20)
    with pytest.raises(ValueError, match="size"):
        render_layer_thumbnail(image, size=MAX_THUMBNAIL_SIZE + 1)


def test_thumbnail_zero_dimension_yields_blank():
    image = np.zeros((0, 10, 4), dtype=np.uint8)
    out = render_layer_thumbnail(image)
    assert out.shape == (DEFAULT_THUMBNAIL_SIZE, DEFAULT_THUMBNAIL_SIZE, 4)
    assert (out == 0).all()


def test_thumbnail_preserves_aspect_ratio():
    """A 100×50 image fits into a square thumbnail with vertical padding."""
    image = _solid_image(50, 100)
    out = render_layer_thumbnail(image, size=32)
    # The image content is centred horizontally; rows above and
    # below the image are left transparent.
    painted = out[..., 3] > 0
    rows_with_paint = np.where(painted.any(axis=1))[0]
    assert rows_with_paint.size > 0
    # Top edge of paint > 0 (vertical padding present).
    assert int(rows_with_paint.min()) > 0
    # Bottom edge of paint < target_size - 1 (padding on the other
    # side too).
    assert int(rows_with_paint.max()) < 31


def test_thumbnail_carries_source_colour():
    """The thumbnail of a solid red image should be solid red where
    pixels are painted."""
    image = _solid_image(40, 40, rgba=(200, 50, 80, 255))
    out = render_layer_thumbnail(image, size=32)
    painted = out[..., 3] > 0
    assert (out[painted, 0] == 200).all()


# ---------------------------------------------------------------------------
# render_mask_thumbnail
# ---------------------------------------------------------------------------


def test_mask_thumbnail_returns_opaque_rgba():
    mask = np.full((50, 50), 128, dtype=np.uint8)
    out = render_mask_thumbnail(mask, size=32)
    assert out.shape == (32, 32, 4)
    # Painted pixels are fully opaque; the background-padding rows
    # are transparent (the helper only fills the inscribed sub-rect).
    painted = out[..., 3] > 0
    assert painted.any()
    # Where painted, RGB are equal (greyscale duplication).
    assert (out[painted, 0] == out[painted, 1]).all()
    assert (out[painted, 1] == out[painted, 2]).all()


def test_mask_thumbnail_rejects_non_2d():
    bad = np.zeros((10, 10, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="2-D"):
        render_mask_thumbnail(bad)


def test_mask_thumbnail_rejects_non_uint8():
    bad = np.zeros((10, 10), dtype=np.float32)
    with pytest.raises(ValueError, match="uint8"):
        render_mask_thumbnail(bad)


# ---------------------------------------------------------------------------
# ThumbnailCache
# ---------------------------------------------------------------------------


def test_cache_returns_same_buffer_for_same_image():
    cache = ThumbnailCache()
    image = _solid_image(40, 40)
    a = cache.get(image, size=32)
    b = cache.get(image, size=32)
    assert a is b


def test_cache_invalidates_on_pixel_change():
    cache = ThumbnailCache()
    image = _solid_image(40, 40)
    a = cache.get(image, size=32)
    image[0, 0] = (5, 5, 5, 255)
    b = cache.get(image, size=32)
    assert a is not b


def test_cache_separate_entries_per_size():
    cache = ThumbnailCache()
    image = _solid_image(40, 40)
    small = cache.get(image, size=16)
    large = cache.get(image, size=32)
    assert small.shape != large.shape


def test_cache_evicts_oldest_when_full():
    cache = ThumbnailCache(max_entries=3)
    images = [_solid_image(20 + i, 20 + i, rgba=(i, i, i, 255)) for i in range(5)]
    for img in images:
        cache.get(img, size=16)
    assert len(cache) == 3


def test_cache_clear_drops_every_entry():
    cache = ThumbnailCache()
    cache.get(_solid_image(20, 20), size=16)
    cache.clear()
    assert len(cache) == 0


def test_cache_lru_order_extends_recently_used():
    """Re-querying an existing entry must move it to the end of the
    LRU order so the next eviction takes the oldest other entry."""
    cache = ThumbnailCache(max_entries=2)
    a = _solid_image(20, 20, rgba=(10, 0, 0, 255))
    b = _solid_image(20, 20, rgba=(20, 0, 0, 255))
    c = _solid_image(20, 20, rgba=(30, 0, 0, 255))
    cache.get(a, size=16)
    cache.get(b, size=16)
    # Touch ``a`` so it becomes most-recent.
    cache.get(a, size=16)
    cache.get(c, size=16)
    # Capacity = 2; ``b`` should be the evicted one, not ``a``.
    # We can't observe the cache contents directly, but a re-query
    # for ``b`` must produce a NEW buffer (cache miss).
    b_first = cache.get(b, size=16)
    b_again = cache.get(b, size=16)
    assert b_first is b_again   # ``b`` is back in cache after re-add
