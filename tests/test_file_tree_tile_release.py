"""_FileTreeView._release_tile_textures must free GPU handles AND keep the
viewer's VRAM accounting in sync.

Deleting an image from the folder tree popped the texture dict but never dropped
``_tile_tex_sizes`` or decremented ``_vram_usage``, so the tile-wall budget
desynced upward on every delete until ``ensure_tile_texture`` refused every new
upload — a blank tile wall. These tests pin the corrected accounting.
"""
from __future__ import annotations

from Imervue.gui.file_tree_view import _FileTreeView


class _FakeViewer:
    def __init__(self):
        self.tile_textures = {"a": 11, "b": 22, "c": 33}
        self._tile_tex_sizes = {"a": 100, "b": 200, "c": 300}
        self._vram_usage = 600
        self.made = 0
        self.done = 0

    def makeCurrent(self):   # noqa: N802 - mirrors Qt's camelCase API
        self.made += 1

    def doneCurrent(self):   # noqa: N802 - mirrors Qt's camelCase API
        self.done += 1


def _patch_gl(monkeypatch, freed, *, has_context=True):
    monkeypatch.setattr("OpenGL.GL.glDeleteTextures", lambda h: freed.extend(h))

    class _FakeCtx:
        @staticmethod
        def currentContext():   # noqa: N802 - mirrors Qt's camelCase API
            return object() if has_context else None

    monkeypatch.setattr("PySide6.QtGui.QOpenGLContext", _FakeCtx)


def test_frees_handles_and_decrements_accounting(monkeypatch):
    freed: list[int] = []
    _patch_gl(monkeypatch, freed)
    viewer = _FakeViewer()

    _FileTreeView._release_tile_textures(viewer, ["a", "c"])

    assert sorted(freed) == [11, 33]              # both GPU handles freed
    assert set(viewer.tile_textures) == {"b"}     # freed paths removed
    assert viewer._tile_tex_sizes == {"b": 200}   # their sizes dropped too
    assert viewer._vram_usage == 200              # 600 - 100 - 300
    assert viewer.made == 1 and viewer.done == 1  # one context switch


def test_unknown_paths_are_noop(monkeypatch):
    freed: list[int] = []
    _patch_gl(monkeypatch, freed)
    viewer = _FakeViewer()

    _FileTreeView._release_tile_textures(viewer, ["missing"])

    assert freed == []                # no GL call for an unknown path
    assert viewer._vram_usage == 600  # accounting untouched
    assert viewer.made == 0           # context never entered


def test_vram_usage_clamped_at_zero(monkeypatch):
    freed: list[int] = []
    _patch_gl(monkeypatch, freed)
    viewer = _FakeViewer()
    viewer._vram_usage = 50           # accounting under-counts the real sizes

    _FileTreeView._release_tile_textures(viewer, ["a", "b", "c"])

    assert viewer._vram_usage == 0    # clamped, never negative
    assert viewer.tile_textures == {}


def test_context_gone_skips_delete_but_still_accounts(monkeypatch):
    """Window torn down: currentContext() is None, so glDeleteTextures is
    skipped, but the dict pop + VRAM decrement still happen so a shutdown
    delete doesn't leave the accounting inflated."""
    freed: list[int] = []
    _patch_gl(monkeypatch, freed, has_context=False)
    viewer = _FakeViewer()

    _FileTreeView._release_tile_textures(viewer, ["a"])

    assert freed == []                       # delete skipped (no live context)
    assert "a" not in viewer.tile_textures
    assert viewer._vram_usage == 500         # 600 - 100, still accounted
