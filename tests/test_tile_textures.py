"""Tests for tile_textures.compute_visible_tile_paths — viewport culling.

Pure geometry; a fake view supplies the cache, layout inputs, and canvas
size. The GL upload / delete paths are excluded by ``# pragma: no cover``
in the production module and are not exercised here.
"""
from __future__ import annotations

import numpy as np

from Imervue.gpu_image_view import tile_textures


class _FakeModel:
    def __init__(self, images):
        self.images = list(images)


class _FakeView:
    def __init__(self, images, cache, canvas=(1000, 1000), thumb=256):
        self.model = _FakeModel(images)
        self.tile_cache = cache
        self.thumbnail_size = thumb
        self.tile_scale = 1.0
        self.tile_padding = 0
        self.grid_offset_x = 0
        self.grid_offset_y = 0
        self._canvas = canvas

    def width(self):
        return self._canvas[0]

    def height(self):
        return self._canvas[1]

    def devicePixelRatio(self):
        return 1.0


def _tile(size=256):
    return np.zeros((size, size, 4), dtype=np.uint8)


def test_empty_cache_returns_empty():
    view = _FakeView(["a", "b"], {})
    assert tile_textures.compute_visible_tile_paths(view) == set()


def test_all_visible_in_large_canvas():
    cache = {"a": _tile(), "b": _tile()}
    view = _FakeView(["a", "b"], cache, canvas=(2000, 2000))
    assert tile_textures.compute_visible_tile_paths(view) == {"a", "b"}


def test_offscreen_tile_excluded():
    cache = {"a": _tile(), "b": _tile()}
    view = _FakeView(["a", "b"], cache, canvas=(2000, 2000))
    # Scroll far down so the second row's tile is well above the viewport.
    view.grid_offset_y = -10000
    visible = tile_textures.compute_visible_tile_paths(view)
    assert "a" not in visible or "b" not in visible


def test_uncached_path_skipped():
    # "b" is in the model but not the cache → never visible.
    cache = {"a": _tile()}
    view = _FakeView(["a", "b"], cache, canvas=(2000, 2000))
    assert tile_textures.compute_visible_tile_paths(view) == {"a"}
