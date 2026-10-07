"""Actual off-screen OpenGL frames for the developer performance scenarios."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator

import numpy as np
from OpenGL import GL
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

from Imervue.gpu_image_view.gl_renderer import GLRenderer
from Imervue.gpu_image_view.texture_upload import upload_rgba_texture


@contextlib.contextmanager
def framebuffer(width: int, height: int) -> Iterator[tuple]:
    """Require an actual GL context; unavailable GL is a failed measurement."""
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        raise RuntimeError("real OpenGL context required")
    surface = QOffscreenSurface()
    surface.setFormat(context.format())
    surface.create()
    if not context.makeCurrent(surface):
        raise RuntimeError("cannot make OpenGL context current")
    target = upload_rgba_texture(np.zeros((height, width, 4), dtype=np.uint8))
    handle = int(GL.glGenFramebuffers(1))
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, handle)
    GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                              GL.GL_TEXTURE_2D, target, 0)
    try:
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("incomplete framebuffer")
        GL.glViewport(0, 0, width, height)
        yield context, surface
    finally:
        GL.glUseProgram(0)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        GL.glDeleteFramebuffers(1, [handle])
        GL.glDeleteTextures([target])
        context.doneCurrent()
        surface.destroy()


def release_renderer(renderer: GLRenderer) -> None:
    """Release shader resources while the owning GL context is current."""
    GL.glUseProgram(0)
    for program in (renderer._tex_prog, renderer._col_prog):
        GL.glDeleteProgram(program)
    GL.glDeleteBuffers(1, [renderer._vbo])


def first_image_frames(path: str, repeats: int) -> dict:
    """Decode, upload full-resolution pixels and finish a real 1080p frame."""
    from Imervue.gpu_image_view.images.image_loader import decode_image_file
    from scripts.performance_support import measure
    with framebuffer(1920, 1080):
        renderer = GLRenderer()
        renderer.init()
        renderer.set_ortho(1920, 1080)

        def display():
            pixels = decode_image_file(path)
            texture = upload_rgba_texture(pixels)
            try:
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                renderer.draw_textured_quad(0, 0, 1920, 1080, texture)
                GL.glFinish()
                if GL.glGetError() != GL.GL_NO_ERROR:
                    raise RuntimeError("image frame has an OpenGL error")
            finally:
                GL.glDeleteTextures([texture])

        try:
            first = measure(display, repeats=1)
            warm = measure(display, repeats=repeats)
            sample = list(GL.glReadPixels(960, 540, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE))
            if sample[-1] != 255:
                raise RuntimeError("image display is transparent")
            return {"first_full_texture_frame": first, "warm_full_texture_frame": warm,
                    "sample_rgba": sample, "renderer": GL.glGetString(GL.GL_RENDERER).decode(),
                    "boundary": ("decode+full upload+shader+finish; "
                                 "OS cache already warm, no widget/HUD")}
        finally:
            release_renderer(renderer)
