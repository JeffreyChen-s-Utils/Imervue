"""Tests for the deep-zoom tile-cache eviction policy.

``tiles_to_evict`` is pure (keys are ``(level, tx, ty)`` tuples), so it is
tested directly without a GL context — the surrounding ``TileManager.get_tile``
uploads textures and needs one.
"""
from __future__ import annotations

from Imervue.image.tile_manager import tiles_to_evict


def _same_level(count, level=2):
    return [(level, i, 0) for i in range(count)]


def test_no_eviction_below_max_cache():
    assert tiles_to_evict(_same_level(2), 2, max_cache=4, hard_cap=512) == []


def test_evicts_other_level_tiles_first():
    # At the cap with mixed levels; caching another level-2 tile evicts the
    # oldest OTHER-level tile and keeps the level-2 working set intact.
    keys = [(1, 0, 0), (1, 1, 0), (2, 0, 0), (2, 1, 0)]  # LRU oldest first
    assert tiles_to_evict(keys, 2, max_cache=4, hard_cap=512) == [(1, 0, 0)]


def test_keeps_same_level_working_set_below_hard_cap():
    # All tiles are the requested level and the cache is at max_cache but under
    # the hard cap — evicting one would drop a tile this frame needs (thrash),
    # so nothing is evicted; the cache is allowed to grow.
    assert tiles_to_evict(_same_level(4), 2, max_cache=4, hard_cap=512) == []


def test_evicts_oldest_only_once_over_hard_cap():
    # Over the hard cap → drop oldest same-level tiles until back under it.
    keys = _same_level(6)
    assert tiles_to_evict(keys, 2, max_cache=4, hard_cap=5) == [(2, 0, 0), (2, 1, 0)]


def test_other_level_eviction_stops_once_under_max_cache():
    # Three other-level + two same-level at max_cache=4: free the oldest
    # other-level tiles only until under the cap (5 -> 3), keeping the newest.
    keys = [(1, 0, 0), (1, 1, 0), (1, 2, 0), (2, 0, 0), (2, 1, 0)]
    assert tiles_to_evict(keys, 2, max_cache=4, hard_cap=512) == [(1, 0, 0), (1, 1, 0)]
