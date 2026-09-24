"""Freeing the puppet canvas's GL caches tolerates a dead context and nothing else.

``_invalidate_buffer_cache`` and ``_invalidate_texture_cache`` run on document
swap and on teardown; a context that is already gone makes PyOpenGL raise
``GLError``, which must not stop the cache from being cleared. Any other error
is a bug and propagates. Driven unbound on fakes, so no GL widget is built.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from OpenGL.error import GLError

from Imervue.puppet import canvas_render as render_mod
from Imervue.puppet.canvas_render import PuppetCanvasRenderMixin


def _raise(exc):
    def _fail(*_args):
        raise exc
    return _fail


def _buffers():
    return SimpleNamespace(_drawable_buffers={"a": {"vert_vbo": 1, "uv_vbo": 2, "idx_ibo": 3}})


def _textures():
    return SimpleNamespace(_texture_cache={"a.png": 9})


def test_buffer_cache_frees_every_vbo(monkeypatch):
    freed: list = []
    monkeypatch.setattr(render_mod, "glDeleteBuffers", lambda _n, ids: freed.extend(ids))
    fake = _buffers()
    PuppetCanvasRenderMixin._invalidate_buffer_cache(fake)
    assert freed == [1, 2, 3]
    assert fake._drawable_buffers == {}


def test_buffer_cache_clears_despite_a_dead_context(monkeypatch):
    monkeypatch.setattr(render_mod, "glDeleteBuffers", _raise(GLError(1282, None)))
    fake = _buffers()
    PuppetCanvasRenderMixin._invalidate_buffer_cache(fake)
    assert fake._drawable_buffers == {}


def test_buffer_cache_propagates_an_unexpected_error(monkeypatch):
    monkeypatch.setattr(render_mod, "glDeleteBuffers", _raise(TypeError("bad id list")))
    with pytest.raises(TypeError):
        PuppetCanvasRenderMixin._invalidate_buffer_cache(_buffers())


def test_texture_cache_clears_despite_a_dead_context(monkeypatch):
    monkeypatch.setattr(render_mod, "glDeleteTextures", _raise(GLError(1282, None)))
    fake = _textures()
    PuppetCanvasRenderMixin._invalidate_texture_cache(fake)
    assert fake._texture_cache == {}


def test_texture_cache_propagates_an_unexpected_error(monkeypatch):
    monkeypatch.setattr(render_mod, "glDeleteTextures", _raise(TypeError("bad id list")))
    with pytest.raises(TypeError):
        PuppetCanvasRenderMixin._invalidate_texture_cache(_textures())
