"""Tests for tile_textures.compute_visible_tile_paths — viewport culling.

Pure geometry; a fake view supplies the cache, layout inputs, and canvas
size. The GL upload / delete paths are excluded by ``# pragma: no cover``
in the production module and are not exercised here.
"""
from __future__ import annotations

import numpy as np
import pytest
from OpenGL.error import GLError

from Imervue.gpu_image_view import tile_textures
from Imervue.gpu_image_view.vram_budget import mipmap_texture_bytes


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


def _budget_view(*, limit=3, used=2):
    view = _FakeView(["visible", "next", "old"],
                     {p: _tile(16) for p in ("visible", "next", "old")},
                     canvas=(16, 15), thumb=16)
    size = mipmap_texture_bytes(16, 16)
    view.tile_textures = {"visible": 10, "old": 11}
    view._tile_tex_sizes = {"visible": size, "old": size}
    view._vram_usage = used * size
    view._vram_limit = limit * size
    view._tile_uploader = None
    return view, size


def _fake_gl(monkeypatch):
    deleted, uploaded = [], []
    monkeypatch.setattr(tile_textures, "glDeleteTextures", deleted.extend)

    def upload(arr, **kwargs):
        uploaded.append(arr)
        return 20

    monkeypatch.setattr(tile_textures, "upload_rgba_texture", upload)
    return deleted, uploaded


def test_new_texture_evicts_offscreen_before_crossing_budget(monkeypatch):
    view, size = _budget_view(limit=2)
    deleted, uploaded = _fake_gl(monkeypatch)
    assert tile_textures.ensure_tile_texture(view, "next", _tile(16))
    assert deleted == [11]
    assert len(uploaded) == 1
    assert view.tile_textures == {"visible": 10, "next": 20}
    assert view._vram_usage == 2 * size
    assert view._tile_tex_sizes == {"visible": size, "next": size}


def test_exact_capacity_does_not_evict(monkeypatch):
    view, size = _budget_view(limit=3)
    deleted, _ = _fake_gl(monkeypatch)
    assert tile_textures.ensure_tile_texture(view, "next", _tile(16))
    assert deleted == []
    assert view._vram_usage == 3 * size


def test_visible_textures_are_not_evicted_to_admit_another(monkeypatch):
    view, _ = _budget_view(limit=2)
    view.model.images = ["visible", "old", "next"]
    view._canvas = (32, 15)
    deleted, uploaded = _fake_gl(monkeypatch)
    assert not tile_textures.ensure_tile_texture(view, "next", _tile(16))
    assert deleted == uploaded == []
    assert view.tile_textures == {"visible": 10, "old": 11}


@pytest.mark.parametrize("limit", [0, 1])
def test_oversized_texture_does_not_destroy_existing_cache(monkeypatch, limit):
    view, _ = _budget_view(limit=limit)
    deleted, uploaded = _fake_gl(monkeypatch)
    assert not tile_textures.ensure_tile_texture(view, "next", _tile(32))
    assert deleted == uploaded == []
    assert view.tile_textures == {"visible": 10, "old": 11}


def test_cached_texture_is_reused_without_accounting_twice(monkeypatch):
    view, size = _budget_view(limit=2)
    deleted, uploaded = _fake_gl(monkeypatch)
    assert tile_textures.ensure_tile_texture(view, "visible", _tile(16))
    assert deleted == uploaded == []
    assert view._vram_usage == 2 * size


def test_prepaint_eviction_preserves_visible_and_correct_usage(monkeypatch):
    view, size = _budget_view(limit=1)
    deleted, uploaded = _fake_gl(monkeypatch)
    tile_textures.evict_if_needed(view)
    assert deleted == [11]
    assert uploaded == []
    assert view.tile_textures == {"visible": 10}
    assert view._vram_usage == size


def test_failed_gl_delete_keeps_handles_and_budget_for_retry(monkeypatch):
    view, size = _budget_view(limit=2)

    def fail(_handles):
        raise GLError(description="lost context")

    monkeypatch.setattr(tile_textures, "glDeleteTextures", fail)
    with pytest.raises(GLError):
        tile_textures.ensure_tile_texture(view, "next", _tile(16))
    assert view.tile_textures == {"visible": 10, "old": 11}
    assert view._tile_tex_sizes == {"visible": size, "old": size}
    assert view._vram_usage == 2 * size


@pytest.mark.parametrize(("offset_x", "offset_y"), [(16, 0), (-16, 0), (0, -16), (0, 15)])
def test_zero_area_viewport_edges_are_not_visible(offset_x, offset_y):
    view = _FakeView(["a"], {"a": _tile(16)}, canvas=(16, 15), thumb=16)
    view.grid_offset_x, view.grid_offset_y = offset_x, offset_y
    assert tile_textures.compute_visible_tile_paths(view) == set()
