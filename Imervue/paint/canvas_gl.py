"""GL lifecycle of the paint canvas.

``initializeGL`` / ``resizeGL`` / ``paintGL``, the show-time and paint-time
fit-to-window recovery, the dead-context guard, and the uploads of the
document composite (full or damage-rect sub-region) and the transparency
checker tile. ``PaintCanvas`` mixes these methods in ahead of
``QOpenGLWidget`` so the Qt overrides keep their names in the MRO.
"""
from __future__ import annotations

import logging
import math

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_LINEAR,
    GL_NEAREST,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_REPEAT,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDeleteTextures,
    glEnable,
    glEnd,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glScalef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameterf,
    glTexParameteri,
    glTexSubImage2D,
    glTranslatef,
    glVertex2f,
    glViewport,
    GL_MODELVIEW,
    GL_PROJECTION,
)
from OpenGL.error import GLError

from Imervue.paint.canvas_overlays import build_checker_pattern
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.system.qt_timers import call_later

# Same logger as the widget module so log records keep their source name.
logger = logging.getLogger("Imervue.paint.canvas")


class PaintCanvasGLMixin:
    """GL setup, per-frame drawing, view-fit recovery and texture uploads."""

    def initializeGL(self) -> None:  # pragma: no cover - GL needs display server
        glClearColor(0.12, 0.12, 0.12, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)

    def showEvent(self, event) -> None:  # pragma: no cover - Qt UI
        """Defer a fit-to-window until after Qt's first layout pass.

        The canvas is hosted inside a QTabWidget that lays out its
        pages asynchronously: the first ``resizeGL`` lands while the
        widget is still at an intermediate size (the tab bar hasn't
        finished sizing the page area), so the fit math anchors to
        that smaller dimension and the canvas ends up half off-
        screen once the layout settles.

        ``QTimer.singleShot(0, …)`` runs after Qt drains its layout
        queue; reasserting ``_fit_pending`` and forcing the next
        ``resizeGL`` / ``paintGL`` to refit catches the post-layout
        size. Cheap because the timer fires once per show.
        """
        super().showEvent(event)
        self._fit_pending = True
        call_later(0, self, self._deferred_fit_after_show)

    def _deferred_fit_after_show(self) -> None:  # pragma: no cover - Qt UI
        """Recompute the fit once Qt has finalised the widget layout."""
        widget_w, widget_h = self._last_resize_size
        if (widget_w, widget_h) == (0, 0):
            widget_w = self.width()
            widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            # Still degenerate — leave _fit_pending set so paintGL's
            # safety net retries on the next paint.
            return
        if self._user_view_locked:
            self._fit_pending = False
            return
        self._reset_view_to_fit(widget_size=(widget_w, widget_h))
        self.update()

    def resizeGL(self, w: int, h: int) -> None:  # pragma: no cover - GL
        # Qt 6 passes ``w`` / ``h`` here in DEVICE pixels (the framebuffer
        # size, computed internally as ``size() * devicePixelRatio()``).
        # We don't trust the parameter convention across Qt minor versions,
        # so the layout math reads ``self.width() / height()`` instead —
        # those are guaranteed logical pixels regardless of Qt version,
        # which keeps the fit calculation in the same coordinate space as
        # the pan / zoom values it produces. Mixing the two (treating
        # device-pixel ``h`` as if it were logical) is what previously
        # left the document anchored at the bottom of the canvas on HiDPI
        # screens — pan_y = (device_h - logical_displayed) / 2 over-shot
        # by a factor of dpr.
        log_w = max(1, int(self.width()))
        log_h = max(1, int(self.height()))
        dev_w = max(1, int(w))
        dev_h = max(1, int(h))
        glViewport(0, 0, dev_w, dev_h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        # Ortho stays in logical pixels so pan / zoom math draws to the
        # right region — the GL pipeline rescales to the device-pixel
        # framebuffer automatically via the viewport.
        glOrtho(0, log_w, log_h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        self._last_resize_size = (log_w, log_h)
        # Re-fit on every resize until the user manually controls the
        # view. ``_fit_pending`` covers the deferred-init case (widget
        # was too small earlier); ``_user_view_locked`` is the user-took-
        # control flag that pins the view once they wheel-zoom or pan.
        if self._fit_pending or not self._user_view_locked:
            self._reset_view_to_fit(widget_size=(log_w, log_h))

    def paintGL(self) -> None:  # pragma: no cover - GL needs display server
        if not self._gl_context_alive():
            return
        composite = self._document.composite()
        if composite is None:
            return
        self._maybe_refit_view()
        if self._needs_upload:
            self._upload_texture(composite)
            self._needs_upload = False
        if self._texture is None:
            return

        h, w = composite.shape[:2]
        glPushMatrix()
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, 0.0)
        glScalef(self._zoom, self._zoom, 1.0)
        # Rotation pivots about the canvas centre so the visual mid
        # stays put — matches the screen↔image conversion math in
        # ``_screen_to_image`` and the View-menu rotate action.
        # ``isclose`` covers tiny accumulated drift from repeated
        # ±15° increments rather than a strict ``!= 0.0``.
        if not math.isclose(self._rotation_deg, 0.0, abs_tol=1e-6):
            glTranslatef(w / 2.0, h / 2.0, 0.0)
            glRotatef(self._rotation_deg, 0.0, 0.0, 1.0)
            glTranslatef(-w / 2.0, -h / 2.0, 0.0)

        self._draw_transparency_backdrop(w, h)
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        self._draw_overlays(w, h)
        glPopMatrix()
        # HUD overlay sits in widget-space (un-rotated) so the user
        # always sees a circular ring at the canvas centre regardless
        # of the canvas rotation. Drawn AFTER popping the modelview.
        if self._size_hud is not None:
            self._draw_size_hud()

    @staticmethod
    def _gl_context_alive() -> bool:  # pragma: no cover - GL needs display server
        """Return False (and clear safely) when no GL context is current.

        Happens on teardown when a queued paint event fires after the
        canvas was detached. Without this guard ``glClear`` returns
        ``GL_INVALID_OPERATION`` which PyOpenGL turns into a GLError
        that can take other tests down with it.
        """
        from PySide6.QtGui import QOpenGLContext
        if QOpenGLContext.currentContext() is None:
            return False
        try:
            glClear(GL_COLOR_BUFFER_BIT)
        except GLError:   # GL context torn down
            return False
        return True

    def _maybe_refit_view(self) -> None:  # pragma: no cover - GL needs display server
        """Recovery path for the deferred-fit case: re-fit when the
        widget grew between the last fit and now while the user hasn't
        taken view control. Handles the QTabWidget intermediate-size
        scenario where the first ``resizeGL`` fired before the tab
        page reached its real width.
        """
        widget_w, widget_h = self._last_resize_size
        if (widget_w, widget_h) == (0, 0):
            widget_w = self.width()
            widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            return
        needs_refit = self._fit_pending or (
            not self._user_view_locked
            and self._fitted_widget_size != (widget_w, widget_h)
        )
        if needs_refit:
            self._reset_view_to_fit(widget_size=(widget_w, widget_h))

    def _upload_checker_texture(self) -> None:  # pragma: no cover - GL only
        """Build / upload the transparency-checker tile to the GPU.

        Called from ``paintGL`` the first time the canvas paints. The
        tile is tiny (``2 * _CHECKER_CELL_PX`` square) so we don't
        bother with sub-uploads — a single ``glTexImage2D`` plus the
        wrap / filter state is enough. ``GL_REPEAT`` makes the same
        tile cover the entire canvas via the texcoord scaling in
        ``paintGL``; ``GL_NEAREST`` keeps the cell edges crisp under
        any zoom.
        """
        try:
            tile = build_checker_pattern()
            tex = int(glGenTextures(1))
            glBindTexture(GL_TEXTURE_2D, tex)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA,
                tile.shape[1], tile.shape[0], 0,
                GL_RGBA, GL_UNSIGNED_BYTE, tile.tobytes(),
            )
            glBindTexture(GL_TEXTURE_2D, 0)
            self._checker_texture = tex
        except GLError:
            logger.warning("Could not upload the checker texture; using a plain backdrop",
                           exc_info=True)
            # Fallback path in paintGL renders the legacy white quad
            # if this stays None.
            self._checker_texture = None

    def _upload_texture(  # pragma: no cover - GL needs display server
        self, composite: np.ndarray,
    ) -> None:
        if composite is None:
            if self._texture is not None:
                glDeleteTextures(1, [self._texture])
                self._texture = None
            return
        h, w = composite.shape[:2]
        first_upload = self._texture is None
        if first_upload:
            self._texture = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._texture)
        if first_upload:
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        damage = self._pending_damage.clipped_to((h, w))
        if (
            first_upload
            or damage.is_empty
            or damage.covers_full((h, w))
        ):
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, composite.tobytes(),
            )
        else:
            # Sub-region upload — only the dirty pixels move across
            # the bus. The slice is materialised into a packed buffer
            # via ``ascontiguousarray`` so the bytes handed to OpenGL
            # are exactly damage.h * damage.w * 4 long; we therefore
            # leave UNPACK_ROW_LENGTH at the default (0 = packed
            # rows). Setting it to ``w`` here would tell GL that each
            # source row is the full canvas wide and trigger a read
            # past the end of the packed buffer.
            sub = np.ascontiguousarray(
                composite[damage.y:damage.y2, damage.x:damage.x2, :],
            )
            glTexSubImage2D(
                GL_TEXTURE_2D, 0,
                damage.x, damage.y, damage.w, damage.h,
                GL_RGBA, GL_UNSIGNED_BYTE,
                sub.tobytes(),
            )
        glBindTexture(GL_TEXTURE_2D, 0)
        self._pending_damage = EMPTY_DAMAGE
