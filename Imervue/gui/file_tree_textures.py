"""Release deleted tile textures and maintain viewer VRAM accounting."""

from __future__ import annotations


def _release_tile_textures(viewer, paths: list[str]) -> None:
    """Free the GL textures for *paths* under a single context switch and
    keep the viewer's VRAM accounting in sync.

    The delete fires from a menu-action event handler, not from within
    ``paintGL``, so the viewer's GL context may not be current. Make it
    current once for the whole batch and swallow the GLError if the
    context is gone entirely (window already destroyed during shutdown).
    Like ``tile_textures.free_tile_textures``, drop each freed path from
    ``_tile_tex_sizes`` and subtract its bytes from ``_vram_usage`` —
    omitting that desynced the budget upward on every tree delete until
    new tile uploads were refused (the blank-wall symptom).
    """
    sizes = getattr(viewer, "_tile_tex_sizes", None)
    textures = []
    freed_bytes = 0
    for p in paths:
        tex = viewer.tile_textures.pop(p, None)
        if tex is None:
            continue
        textures.append(tex)
        if sizes is not None:
            freed_bytes += sizes.pop(p, 0)
    if not textures:
        return
    from OpenGL.error import GLError
    from OpenGL.GL import glDeleteTextures
    from PySide6.QtGui import QOpenGLContext

    try:
        if hasattr(viewer, "makeCurrent"):
            viewer.makeCurrent()
        if QOpenGLContext.currentContext() is not None:
            glDeleteTextures(textures)
    except (GLError, RuntimeError):  # context or widget already torn down; nothing to free
        pass
    finally:
        if hasattr(viewer, "doneCurrent"):
            viewer.doneCurrent()
    if hasattr(viewer, "_vram_usage"):
        viewer._vram_usage = max(0, viewer._vram_usage - freed_bytes)
