"""Actual OpenGL wall rendering under a deliberately tiny texture budget."""
from __future__ import annotations

import contextlib
from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

from Imervue.gpu_image_view import tile_textures
from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.gpu_image_view.texture_upload import upload_rgba_texture
from Imervue.gpu_image_view.tile_grid_renderer import TileGridRenderer
from Imervue.gpu_image_view.vram_budget import mipmap_texture_bytes

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture
def gl_surface(qapp, record_property):
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    assert context.create(), "A real OpenGL context is required"
    surface = QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    assert context.makeCurrent(surface)
    record_property("gl_renderer", GL.glGetString(GL.GL_RENDERER).decode())
    target = upload_rgba_texture(np.zeros((15, 32, 4), dtype=np.uint8))
    framebuffer = int(GL.glGenFramebuffers(1))
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, framebuffer)
    GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                              GL.GL_TEXTURE_2D, target, 0)
    assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) == GL.GL_FRAMEBUFFER_COMPLETE
    GL.glViewport(0, 0, 32, 15)
    try:
        yield context, surface
    finally:
        GL.glUseProgram(0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glDeleteFramebuffers(1, [framebuffer])
        GL.glDeleteTextures([target])
        context.doneCurrent()
        surface.destroy()


def _view(context, surface):
    images = [f"tile-{i}" for i in range(20)]
    cache = {}
    for i, path in enumerate(images):
        array = np.empty((16, 16, 4), dtype=np.uint8)
        array[:] = (100 + i * 3, 50 + i * 2, 25 + i, 255)
        cache[path] = array
    renderer = GLRenderer()
    renderer.init()
    assert renderer.use_shaders
    renderer.set_ortho(32, 15)
    view = SimpleNamespace(
        model=SimpleNamespace(images=images), tile_cache=cache,
        thumbnail_size=16, tile_scale=1.0, tile_padding=0,
        grid_offset_x=0, grid_offset_y=0,
        width=lambda: 32, height=lambda: 15, devicePixelRatio=lambda: 1.0,
        tile_textures={}, _tile_tex_sizes={}, _vram_usage=0,
        _vram_limit=3 * mipmap_texture_bytes(16, 16), _tile_uploader=None,
        renderer=renderer, _tile_load_times={}, offline_paths=set(),
        tile_selection_mode=False, focused_tile_index=-1,
        _drag_selecting=False, _drag_start_pos=None, _drag_end_pos=None,
    )

    @contextlib.contextmanager
    def current():
        assert context.makeCurrent(surface)
        yield

    view._current_gl_context = current
    view._ensure_tile_texture = lambda path, data: tile_textures.ensure_tile_texture(view, path, data)
    view._evict_tile_textures_if_needed = lambda: tile_textures.evict_if_needed(view)
    return view


def _release(view):
    tile_textures.delete_all_tile_textures(view)
    GL.glUseProgram(0)
    for program in (view.renderer._tex_prog, view.renderer._col_prog):
        GL.glDeleteProgram(program)
    GL.glDeleteBuffers(1, [view.renderer._vbo])


def test_full_budget_scroll_renders_every_new_row(gl_surface):
    view = _view(*gl_surface)
    wall = TileGridRenderer(view)
    try:
        for row in [*range(10), *range(9, -1, -1)]:
            view.grid_offset_y = -row * 16
            GL.glClearColor(0, 0, 0, 1)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            wall.paint()
            pixels = GL.glReadPixels(0, 0, 32, 15, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            image = np.frombuffer(pixels, dtype=np.uint8).reshape(15, 32, 4)
            for col in range(2):
                path = view.model.images[row * 2 + col]
                assert path in view.tile_textures
                np.testing.assert_allclose(image[7, col * 16 + 8], view.tile_cache[path][7, 8], atol=1)
            assert view._vram_usage <= view._vram_limit
            assert view._vram_usage == sum(view._tile_tex_sizes.values())
            assert GL.glGetError() == GL.GL_NO_ERROR
    finally:
        _release(view)


def test_texture_release_frees_actual_gl_handles(gl_surface):
    view = _view(*gl_surface)
    try:
        TileGridRenderer(view).paint()
        handles = list(view.tile_textures.values())
        assert handles and all(GL.glIsTexture(handle) for handle in handles)
        tile_textures.delete_all_tile_textures(view)
        assert not any(GL.glIsTexture(handle) for handle in handles)
        assert view._vram_usage == 0
        assert view._tile_tex_sizes == {}
        assert GL.glGetError() == GL.GL_NO_ERROR
    finally:
        _release(view)
