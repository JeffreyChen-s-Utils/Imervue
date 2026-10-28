"""Shared-context GL state preservation and framebuffer attachment requirements."""
from __future__ import annotations

import contextlib
from OpenGL.GL import (
    GL_COLOR_CLEAR_VALUE, GL_VIEWPORT, GL_MODELVIEW, GL_PROJECTION,
    glGetFloatv, glGetIntegerv, glMatrixMode, glPushMatrix, glPopMatrix,
    glClearColor, glViewport,
)

@contextlib.contextmanager
def _preserved_gl_render_state():
    """Save and restore the clear colour, viewport, and matrix stacks.

    An off-screen puppet render (virtual camera / NDI) shares the widget's GL
    context, but the visible ``paintGL`` only issues ``glClear`` and depends on
    the clear colour set once in ``initializeGL`` and the viewport set in
    ``resizeGL``. Leaving the off-screen clear colour/viewport in place therefore
    bled into the next on-screen frame — most visibly turning the desktop pet
    into a solid magenta box for the whole time the virtual camera streamed, and
    mis-sizing the editor render. Restoring on exit — even when the body returns
    early or raises — also balances the projection/modelview pushes that a
    zero-sized document used to leak until ``GL_STACK_OVERFLOW``.
    """
    prev_clear = glGetFloatv(GL_COLOR_CLEAR_VALUE)
    prev_viewport = glGetIntegerv(GL_VIEWPORT)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    try:
        yield
    finally:
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glClearColor(*(float(c) for c in prev_clear))
        glViewport(*(int(v) for v in prev_viewport))


def offscreen_framebuffer_format():
    """The format of ``render_offscreen_puppet``'s framebuffer: with a depth-stencil attachment.

    Clip masks draw through the stencil buffer; a framebuffer without one
    ignored them, so every recording, snapshot and stream showed clipped
    drawables (irises, hair shadows) spilling past their masks.
    """
    from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
    fmt = QOpenGLFramebufferObjectFormat()
    fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
    return fmt
