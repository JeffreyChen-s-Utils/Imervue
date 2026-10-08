"""Shared viewport bounds agree with brute-force geometry at all grid edges."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.gpu_image_view.tile_textures import compute_visible_tile_paths
from Imervue.gpu_image_view.tile_viewport import TileViewport, record_tile_extent, viewport_for


@pytest.mark.parametrize("offset", [(0, 0), (-40, -200), (40, 200), (-900, -10_000)])
@pytest.mark.parametrize("count", [0, 1, 17, 1000])
@pytest.mark.parametrize("extent", [(100, 100), (300, 500)])
def test_candidate_math_matches_full_grid_intersection(offset, count, extent):
    viewport = TileViewport(count, 5, 110, 1, 100, 530, 330, *offset, extent)
    expected = set()
    for index in range(count):
        x, y = viewport.origin(index)
        if x + extent[0] > 0 and x < viewport.width and y + extent[1] > 0 and y < viewport.height:
            expected.add(index)
    assert set(viewport.indices(buffer=0)) == expected
    assert expected <= set(viewport.indices(buffer=1))
    assert len(set(viewport.indices())) <= 70


def test_edge_contact_zero_viewport_invalid_cell_and_partial_last_row():
    assert list(TileViewport(20, 2, 100, 1, 100, 100, 100, 0, -100, (100, 100))
                .indices(buffer=0)) == [2]
    for width, height, cell in [(0, 100, 100), (100, 0, 100), (100, 100, 0),
                                (100, 100, float("nan"))]:
        assert not list(TileViewport(20, 2, cell, 1, 100, width, height, 0, 0, (100, 100))
                        .indices())
    viewport = TileViewport(7, 5, 100, 1, 100, 1000, 1000, 0, 0, (100, 100))
    assert list(viewport.indices()) == list(range(7))


@pytest.mark.parametrize("dpr", [1., 1.25, 2.])
@pytest.mark.parametrize("scale", [.25, 1., 3.])
def test_cached_rectangles_use_actual_dimensions_including_large_svg(dpr, scale):
    images = [str(i) for i in range(50)]
    cache = {path: np.zeros((40 + (i % 4) * 50, 60 + (i % 3) * 100, 4), dtype=np.uint8)
             for i, path in enumerate(images)}
    view = SimpleNamespace(
        model=SimpleNamespace(images=images), thumbnail_size=128, tile_cache=cache,
        tile_scale=scale, tile_padding=5, grid_offset_x=-27., grid_offset_y=-260.,
        width=lambda: 530, height=lambda: 330, devicePixelRatio=lambda: dpr,
        _tile_max_dimensions=(0, 0),
    )
    for array in cache.values():
        record_tile_extent(view, array)
    viewport = viewport_for(view)
    expected = set()
    for index, path in enumerate(images):
        x, y = viewport.origin(index)
        h, w = cache[path].shape[:2]
        if x + w * viewport.draw_scale > 0 and x < 530 and y + h * viewport.draw_scale > 0 and y < 330:
            expected.add(path)
    assert compute_visible_tile_paths(view) == expected


def test_eviction_never_iterates_model_and_frame_geometry_is_reused():
    class IndexedImages(list):
        def __iter__(self):
            raise AssertionError("visibility scanned the model")

    images = IndexedImages(str(i) for i in range(100_000))
    view = SimpleNamespace(
        model=SimpleNamespace(images=images), thumbnail_size=128, tile_cache={},
        tile_scale=1., tile_padding=8, grid_offset_x=0., grid_offset_y=-500_000.,
        width=lambda: 1920, height=lambda: 1080, devicePixelRatio=lambda: 1.,
        _tile_max_dimensions=(128, 128),
    )
    frame = viewport_for(view)
    for index in frame.indices():
        view.tile_cache[images[index]] = np.ones((128, 128, 4), dtype=np.uint8)
    view._frame_tile_viewport = frame
    assert viewport_for(view) is frame
    assert compute_visible_tile_paths(view)


def test_full_size_auto_base_and_extent_fallback_handles_empty_cache():
    view = SimpleNamespace(model=SimpleNamespace(images=["a"]), thumbnail_size=None,
                           tile_cache={"a": np.zeros((32, 64, 4), dtype=np.uint8)})
    assert viewport_for(view).base == 64
    view.tile_cache.clear()
    assert viewport_for(view).base == 256
