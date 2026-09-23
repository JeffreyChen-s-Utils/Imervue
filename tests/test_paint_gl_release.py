"""Freeing paint GL objects off paintGL tolerates a dead context and nothing else.

``set_onion_skin_source`` and ``_release_grid_vbo`` run outside ``paintGL``; a
context that is already gone makes PyOpenGL raise ``GLError``, which is expected
and must not stop the handle from being dropped. Any other error is a bug and
propagates. Driven unbound on fakes, so no GL widget is built.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest
from OpenGL.error import GLError

from Imervue.paint import canvas as canvas_mod
from Imervue.paint import canvas_overlays as overlays_mod
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.canvas_overlays import PaintCanvasOverlaysMixin


def _raise(exc):
    def _fail(*_args):
        raise exc
    return _fail


def _onion_canvas():
    return SimpleNamespace(_onion_skin_texture=7, _onion_skin_source=None,
                           _onion_skin_buffer_id=3,
                           _current_gl_context=contextlib.nullcontext)


def _grid_canvas():
    return SimpleNamespace(_grid_vbo=5, _grid_vbo_size=(10, 10), _grid_vbo_vertices=8)


def test_onion_skin_swap_frees_the_texture(monkeypatch):
    freed: list = []
    monkeypatch.setattr(canvas_mod, "glDeleteTextures", lambda _n, ids: freed.extend(ids))
    fake = _onion_canvas()
    source = object()
    PaintCanvas.set_onion_skin_source(fake, source)
    assert freed == [7]
    assert (fake._onion_skin_source, fake._onion_skin_texture, fake._onion_skin_buffer_id) == (
        source, None, None)


def test_onion_skin_swap_survives_a_dead_context(monkeypatch):
    monkeypatch.setattr(canvas_mod, "glDeleteTextures", _raise(GLError(1282, None)))
    fake = _onion_canvas()
    PaintCanvas.set_onion_skin_source(fake, None)
    assert fake._onion_skin_texture is None


def test_onion_skin_swap_propagates_an_unexpected_error(monkeypatch):
    monkeypatch.setattr(canvas_mod, "glDeleteTextures", _raise(TypeError("bad id list")))
    with pytest.raises(TypeError):
        PaintCanvas.set_onion_skin_source(_onion_canvas(), None)


def test_grid_vbo_release_survives_a_dead_context(monkeypatch):
    monkeypatch.setattr(overlays_mod, "glDeleteBuffers", _raise(GLError(1282, None)))
    fake = _grid_canvas()
    PaintCanvasOverlaysMixin._release_grid_vbo(fake)
    assert (fake._grid_vbo, fake._grid_vbo_size, fake._grid_vbo_vertices) == (None, None, 0)


def test_grid_vbo_release_propagates_an_unexpected_error(monkeypatch):
    monkeypatch.setattr(overlays_mod, "glDeleteBuffers", _raise(TypeError("bad id list")))
    with pytest.raises(TypeError):
        PaintCanvasOverlaysMixin._release_grid_vbo(_grid_canvas())
