"""Large walls draw candidates only, with no whole-library iteration per frame."""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view import tile_grid_renderer as module


def test_frame_never_walks_the_entire_library(monkeypatch):
    class IndexedImages(list):
        def __iter__(self):
            raise AssertionError("whole-library traversal in a frame")

    images = IndexedImages(str(i) for i in range(100_000))
    view = SimpleNamespace(
        model=SimpleNamespace(images=images), thumbnail_size=128, tile_cache={},
        tile_scale=1., tile_padding=8, grid_offset_x=0., grid_offset_y=-500_000.,
        width=lambda: 1920, height=lambda: 1080, devicePixelRatio=lambda: 1.,
        _evict_tile_textures_if_needed=lambda: None, tile_selection_mode=False,
        focused_tile_index=0, focus_ring_visible=False, _drag_selecting=False,
    )
    monkeypatch.setattr(module, "glLoadIdentity", lambda: None)
    monkeypatch.setattr(module, "glPixelStorei", lambda *args: None)
    renderer = module.TileGridRenderer(view)
    visited = []
    monkeypatch.setattr(renderer, "_draw_single", lambda i, *args: visited.append(i))
    renderer.paint()
    assert 0 < len(visited) < 200
    assert min(visited) > 50_000
