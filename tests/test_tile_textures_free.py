"""free_tile_textures must free GPU handles under a current GL context AND keep
the VRAM accounting in sync.

Tile-wall textures were freed off paintGL with a bare glDeleteTextures (silently
dropped -> leak) and, on the batch-rename / move / rotate paths, merely popped
from the dict (orphaned on the GPU) without decrementing _vram_usage. The budget
then stayed inflated until ensure_tile_texture refused every new upload -> a
blank tile wall.
"""
from __future__ import annotations

import contextlib

from Imervue.gpu_image_view import tile_textures


class _FakeView:
    def __init__(self):
        self.tile_textures = {"a": 11, "b": 22, "c": 33}
        self._tile_tex_sizes = {"a": 100, "b": 200, "c": 300}
        self._vram_usage = 600
        self.made_current = 0

    @contextlib.contextmanager
    def _current_gl_context(self):
        self.made_current += 1
        yield


def test_frees_handles_and_decrements_accounting(monkeypatch):
    freed: list[int] = []
    monkeypatch.setattr(
        tile_textures, "glDeleteTextures", lambda handles: freed.extend(handles),
    )
    view = _FakeView()

    tile_textures.free_tile_textures(view, ["a", "c"])

    assert sorted(freed) == [11, 33]              # both GPU handles freed
    assert view.made_current == 1                 # under a current GL context
    assert set(view.tile_textures) == {"b"}       # freed paths removed
    assert view._tile_tex_sizes == {"b": 200}     # their sizes dropped too
    assert view._vram_usage == 200                # 600 - 100 - 300


def test_no_op_leaves_accounting_and_context_untouched(monkeypatch):
    called: list = []
    monkeypatch.setattr(
        tile_textures, "glDeleteTextures", lambda h: called.append(h),
    )
    view = _FakeView()

    tile_textures.free_tile_textures(view, ["missing"])

    assert called == []              # no GL call for an unknown path
    assert view.made_current == 0    # context never entered
    assert view._vram_usage == 600   # accounting untouched


def test_vram_usage_clamped_at_zero(monkeypatch):
    monkeypatch.setattr(tile_textures, "glDeleteTextures", lambda h: None)
    view = _FakeView()
    view._vram_usage = 50            # accounting under-counts the real sizes

    tile_textures.free_tile_textures(view, ["a", "b", "c"])

    assert view._vram_usage == 0     # clamped, never goes negative
    assert view.tile_textures == {}
