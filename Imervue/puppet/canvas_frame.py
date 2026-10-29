"""Onscreen and offscreen frame orchestration and pet rendering profile."""
from __future__ import annotations

from typing import TYPE_CHECKING
from OpenGL.GL import (
    GL_BLEND, GL_COLOR_BUFFER_BIT, GL_TEXTURE_2D, GL_MODELVIEW, GL_PROJECTION,
    glClear, glClearColor, glEnable, glLoadIdentity, glMatrixMode, glOrtho,
    glPopMatrix, glPushMatrix, glScalef, glTranslatef, glViewport,
)
from Imervue.puppet.canvas_gl_state import _preserved_gl_render_state, offscreen_framebuffer_format
from Imervue.puppet.canvas_view import _fit_scale_and_pan
if TYPE_CHECKING:
    from PySide6.QtGui import QImage


class PuppetCanvasFrameMixin:
    """Onscreen and offscreen frame orchestration and pet rendering profile."""

    def _current_gl_context(self):
        """Current this widget's GL context for texture/buffer frees issued
        outside ``paintGL`` (document swap runs from file-open / undo / a network
        or timer callback), so ``glDelete*`` isn't dropped and the resource
        leaked."""
        from Imervue.gpu_image_view.gl_context import make_current_guard
        return make_current_guard(self)

    def initializeGL(self) -> None:  # pragma: no cover - GL needs display
        if self._pet_mode:
            # Fully transparent clear — paintGL skips the checker so
            # every non-puppet pixel reaches the host window's
            # translucent background and the desktop shows through.
            glClearColor(0.0, 0.0, 0.0, 0.0)
        else:
            glClearColor(0.13, 0.13, 0.15, 1.0)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)

    def resizeGL(self, w: int, h: int) -> None:  # pragma: no cover - GL needs display
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, w, h, 0, -1, 1)   # y-down so puppet-canvas-space matches image-space
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def paintGL(self) -> None:  # pragma: no cover - GL needs display
        glClear(GL_COLOR_BUFFER_BIT)
        if self._document is None:
            return
        self._maybe_refit_view()
        glPushMatrix()
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, 0.0)
        glScalef(self._zoom, self._zoom, 1.0)
        # Desktop-pet mode skips the editor's transparency checker
        # backdrop — the host window is translucent and the desktop
        # itself fills the role of "background" — and also drops the
        # selection overlay since the pet has no editor UI.
        if self._pet_mode:
            if self._pet_shadow_enabled:
                self._draw_pet_shadow()
            self._draw_drawables()
        else:
            self._draw_transparency_backdrop()
            self._draw_drawables()
            self._draw_selection_overlay()
        glPopMatrix()

    def render_offscreen_puppet(   # pragma: no cover - GL needs display
        self,
        width: int,
        height: int,
        *,
        background_rgba: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    ) -> QImage | None:
        """Render JUST the puppet to an off-screen FBO and return it
        as a QImage.

        Skips the transparency checker, the editor selection overlay,
        and the workspace chrome — perfect for the streaming outputs
        which want "character only on a known background colour" so
        OBS can composite or chroma-key it. The puppet is centred +
        scaled to fit the FBO preserving aspect ratio (so the entire
        document canvas always lands inside the streamed frame, no
        cropping, regardless of how the user has the workspace
        zoomed / panned).

        ``background_rgba`` controls what fills the area outside the
        puppet's drawables. The default ``(0, 0, 0, 0)`` is fully
        transparent — NDI honours it, RGB-only virtual cameras lose
        the alpha and end up with black. Pass a solid colour like
        ``(1.0, 0.0, 1.0, 1.0)`` (magenta) to give virtual-camera
        users something they can OBS-Color-Key out.
        """
        if self._document is None or width <= 0 or height <= 0:
            return None
        from PySide6.QtOpenGL import QOpenGLFramebufferObject

        self.makeCurrent()
        fbo = None
        try:
            fbo = QOpenGLFramebufferObject(width, height, offscreen_framebuffer_format())
            if not fbo.bind():
                return None
            try:
                # The context manager snapshots the visible canvas's clear
                # colour / viewport / matrix stacks and restores them on exit,
                # so this shared-context off-screen render can't corrupt the
                # next on-screen paintGL — even on the early return below.
                with _preserved_gl_render_state():
                    if not self._render_puppet_frame(width, height, background_rgba):
                        return None
                    return fbo.toImage()
            finally:
                fbo.release()
        finally:
            # Destroy the FBO while the context is still current — its C++
            # destructor needs one, or Qt leaks the FBO's texture/renderbuffer
            # on every call (once per NDI / virtual-camera frame).
            fbo = None
            self.doneCurrent()

    def _render_puppet_frame(   # pragma: no cover - GL needs display
        self, width: int, height: int,
        background_rgba: tuple[float, float, float, float],
    ) -> bool:
        """Draw the document fitted into a ``width`` x ``height`` target.

        Sets a pixel-space ortho projection, fits the document with
        :func:`_fit_scale_and_pan`, clears to ``background_rgba`` and draws
        the drawables. Returns ``False``, after the projection is set but
        before clearing, when the document has no area.
        """
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, height, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        fit = _fit_scale_and_pan(self._document.size, width, height)
        if fit is None:
            return False
        scale, pan_x, pan_y = fit
        glTranslatef(pan_x, pan_y, 0.0)
        glScalef(scale, scale, 1.0)

        # Clear to the requested background (transparent by
        # default). The checker backdrop is intentionally NOT
        # drawn — streamers chose the virtual-camera / NDI
        # path because they want the character composited
        # over their own scene.
        r, g, b, a = background_rgba
        glClearColor(float(r), float(g), float(b), float(a))
        glClear(GL_COLOR_BUFFER_BIT)

        self._draw_drawables()
        return True

    def set_pet_shadow(
        self,
        *,
        enabled: bool,
        opacity: float = 1.0,
        scale: float = 1.0,
    ) -> None:
        """Configure the drop shadow drawn under the puppet in pet
        mode. ``opacity`` multiplies the texture's built-in falloff
        (so ``1.0`` is the default-look shadow, ``0.5`` half-fade);
        ``scale`` scales the shadow ellipse width."""
        self._pet_shadow_enabled = bool(enabled)
        self._pet_shadow_opacity = max(0.0, min(1.0, float(opacity)))
        self._pet_shadow_scale = max(0.0, float(scale))
        self.update()

    def pet_shadow_enabled(self) -> bool:
        return self._pet_shadow_enabled
