"""GL canvas for the Puppet tab — Phase 2 draws the loaded
``PuppetDocument`` as a static textured-triangle stack with no
deformation. Later phases (parameters / motions / physics) will pipe
per-frame vertex offsets into the same draw path.

Reuses ``Imervue.paint.canvas`` GL conventions (DPR-scaled viewport,
ortho projection in image-space pixels, transparency-checker backdrop,
pan/zoom on wheel/middle-drag) so the two GL widgets behave the same
to the user. Kept deliberately small — heavy logic is on the Qt-free
``render_prep`` and ``document`` modules so we can unit-test without
spinning up a context.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_DST_COLOR,
    GL_LINEAR,
    GL_ONE,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glColor4f,
    glDeleteTextures,
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glScalef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glTranslatef,
    glVertex2f,
    glViewport,
    GL_MODELVIEW,
    GL_PROJECTION,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from puppet.document import PuppetDocument
from puppet.render_prep import (
    DrawCommand,
    build_draw_list,
    fit_view,
)
from puppet.runtime import (
    apply_expressions,
    compose_all_drawables,
    default_parameter_values,
    resolve_pose_visibility,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent, QWheelEvent


logger = logging.getLogger("Imervue.plugin.puppet.canvas")

_ZOOM_STEP = 1.15
_MIN_ZOOM = 0.05
_MAX_ZOOM = 32.0
_CHECKER_TILE = 16


_BLEND_FUNCS = {
    "normal": (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA),
    "additive": (GL_SRC_ALPHA, GL_ONE),
    "multiply": (GL_DST_COLOR, GL_ONE_MINUS_SRC_ALPHA),
}


class PuppetCanvas(QOpenGLWidget):
    """QOpenGLWidget that renders one ``PuppetDocument`` at a time.

    Static-mesh only in Phase 2 — vertex deformation hooks land in
    Phase 4. The canvas owns the GL textures and the pan/zoom state;
    everything else (drawables, parameters) lives on the document.
    """

    document_loaded = Signal()
    zoom_changed = Signal(float)
    parameters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document: PuppetDocument | None = None
        self._draw_list: list[DrawCommand] = []
        self._texture_cache: dict[str, int] = {}
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._user_view_locked: bool = False
        self._panning: bool = False
        self._pan_anchor: tuple[float, float] = (0.0, 0.0)
        self._parameter_values: dict[str, float] = {}
        # Active expressions in priority order — last item wins on
        # overlapping parameter overrides. Editor toggles set / clear
        # entries via add_expression / remove_expression.
        self._active_expressions: list = []
        # Pose group → active drawable id. The render path hides every
        # other member of the group so users can flip between weapon
        # variants / mouth shapes / etc. without juggling visibility.
        self._active_pose: dict[str, str] = {}
        # Cache of deformed vertex arrays keyed by drawable id; rebuilt
        # whenever parameter values change so paintGL can read it
        # without re-running the composer per call.
        self._deformed_vertices: dict[str, np.ndarray] = {}
        self._visibility: dict[str, bool] = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ---- public API -----------------------------------------------------

    def load_document(self, document: PuppetDocument | None) -> None:
        """Bind ``document`` to the canvas. Pass ``None`` to clear.

        Texture cache is invalidated on every document swap; the next
        ``paintGL`` re-uploads everything against the bound document's
        ``textures`` map. Parameter values reset to each parameter's
        ``default``.
        """
        self._document = document
        self._draw_list = build_draw_list(document) if document is not None else []
        self._invalidate_texture_cache()
        self._user_view_locked = False
        self._parameter_values = (
            default_parameter_values(document) if document is not None else {}
        )
        self._active_expressions = []
        self._active_pose = {}
        self._recompute_deformed_vertices()
        self.document_loaded.emit()
        self.parameters_changed.emit()
        self.update()

    def document(self) -> PuppetDocument | None:
        return self._document

    def parameter_values(self) -> dict[str, float]:
        return dict(self._parameter_values)

    def set_parameter_value(self, param_id: str, value: float) -> None:
        """Push a slider / motion / physics output into the parameter
        bag. Triggers a per-frame vertex recomposition + redraw."""
        if self._document is None:
            return
        if param_id not in self._parameter_values:
            return
        self._parameter_values[param_id] = float(value)
        self._recompute_deformed_vertices()
        self.update()

    def reset_parameters(self) -> None:
        """Restore every parameter to its authored default."""
        if self._document is None:
            return
        self._parameter_values = default_parameter_values(self._document)
        self._recompute_deformed_vertices()
        self.parameters_changed.emit()
        self.update()

    def reset_view(self) -> None:
        """Recompute fit-to-window pan/zoom on the next paint."""
        self._user_view_locked = False
        self.update()

    def zoom_factor(self) -> float:
        return self._zoom

    def _recompute_deformed_vertices(self) -> None:
        if self._document is None:
            self._deformed_vertices = {}
            self._visibility = {}
            return
        active_values = apply_expressions(
            self._parameter_values, self._active_expressions,
        )
        if active_values:
            self._deformed_vertices = compose_all_drawables(
                self._document, active_values,
            )
        else:
            self._deformed_vertices = {}
        # Pose visibility applies even when there are no parameters —
        # users may have a static rig with weapon-swap pose groups.
        self._visibility = resolve_pose_visibility(
            self._document, self._active_pose,
        )

    # ---- expression / pose API -----------------------------------------

    def add_expression(self, name: str) -> bool:
        """Push an expression by name onto the active stack. No-op if
        the document doesn't have that expression or it's already on."""
        if self._document is None:
            return False
        match = next(
            (e for e in self._document.expressions if e.name == name), None,
        )
        if match is None:
            return False
        if any(e.name == name for e in self._active_expressions):
            return False
        self._active_expressions.append(match)
        self._recompute_deformed_vertices()
        self.update()
        return True

    def remove_expression(self, name: str) -> bool:
        before = len(self._active_expressions)
        self._active_expressions = [
            e for e in self._active_expressions if e.name != name
        ]
        if len(self._active_expressions) == before:
            return False
        self._recompute_deformed_vertices()
        self.update()
        return True

    def active_expressions(self) -> list[str]:
        return [e.name for e in self._active_expressions]

    def set_pose_active(self, group_id: str, drawable_id: str) -> bool:
        """Pick which drawable in a pose group is currently visible."""
        if self._document is None:
            return False
        group = next(
            (g for g in self._document.pose_groups if g.id == group_id), None,
        )
        if group is None or drawable_id not in group.drawables:
            return False
        self._active_pose[group_id] = drawable_id
        self._recompute_deformed_vertices()
        self.update()
        return True

    def active_pose(self) -> dict[str, str]:
        return dict(self._active_pose)

    def visibility(self) -> dict[str, bool]:
        return dict(self._visibility)

    # ---- GL lifecycle ---------------------------------------------------

    def initializeGL(self) -> None:  # pragma: no cover - GL needs display
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
        self._draw_transparency_backdrop()
        self._draw_drawables()
        glPopMatrix()

    # ---- rendering ------------------------------------------------------

    def _maybe_refit_view(self) -> None:  # pragma: no cover - GL needs display
        if self._user_view_locked:
            return
        size = self._device_pixel_size()
        if self._document is None:
            return
        self._zoom, self._pan_x, self._pan_y = fit_view(
            size, self._document.size,
        )

    def _device_pixel_size(self) -> tuple[int, int]:  # pragma: no cover - Qt edge
        ratio = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        return int(self.width() * ratio), int(self.height() * ratio)

    def _draw_transparency_backdrop(self) -> None:  # pragma: no cover - GL needs display
        if self._document is None:
            return
        w, h = self._document.size
        glDisable(GL_TEXTURE_2D)
        light = (0.18, 0.18, 0.20, 1.0)
        dark = (0.13, 0.13, 0.15, 1.0)
        for y in range(0, h, _CHECKER_TILE):
            for x in range(0, w, _CHECKER_TILE):
                tile_dark = ((x // _CHECKER_TILE) + (y // _CHECKER_TILE)) % 2 == 0
                glColor4f(*(dark if tile_dark else light))
                glBegin(GL_QUADS)
                glVertex2f(x, y)
                glVertex2f(min(x + _CHECKER_TILE, w), y)
                glVertex2f(min(x + _CHECKER_TILE, w), min(y + _CHECKER_TILE, h))
                glVertex2f(x, min(y + _CHECKER_TILE, h))
                glEnd()
        glEnable(GL_TEXTURE_2D)

    def _draw_drawables(self) -> None:  # pragma: no cover - GL needs display
        for cmd in self._draw_list:
            visible = self._visibility.get(cmd.drawable_id, cmd.visible)
            if not visible:
                continue
            tex_id = self._texture_for(cmd.texture)
            if tex_id is None:
                continue
            sfactor, dfactor = _BLEND_FUNCS.get(cmd.blend_mode, _BLEND_FUNCS["normal"])
            glBlendFunc(sfactor, dfactor)
            glColor4f(1.0, 1.0, 1.0, cmd.opacity)
            glBindTexture(GL_TEXTURE_2D, tex_id)
            verts = self._deformed_vertices.get(cmd.drawable_id, cmd.vertices)
            self._draw_indexed(verts, cmd.uvs, cmd.indices)

    @staticmethod
    def _draw_indexed(  # pragma: no cover - GL needs display
        vertices: np.ndarray, uvs: np.ndarray, indices: np.ndarray,
    ) -> None:
        # Immediate mode keeps Phase 2's render path readable; VBO/VAO
        # plumbing arrives in Phase 4 once we start mutating per-vertex
        # data each frame and immediate mode becomes the bottleneck.
        glBegin(GL_TRIANGLES)
        for idx in indices:
            u, v = uvs[idx]
            x, y = vertices[idx]
            glTexCoord2f(float(u), float(v))
            glVertex2f(float(x), float(y))
        glEnd()

    # ---- texture cache --------------------------------------------------

    def _texture_for(self, path: str) -> int | None:  # pragma: no cover - GL needs display
        cached = self._texture_cache.get(path)
        if cached is not None:
            return cached
        if self._document is None:
            return None
        png_bytes = self._document.textures.get(path)
        if png_bytes is None:
            logger.warning("texture %r not in document", path)
            return None
        tex = self._upload_texture(png_bytes)
        if tex is not None:
            self._texture_cache[path] = tex
        return tex

    def _upload_texture(self, png_bytes: bytes) -> int | None:  # pragma: no cover - GL needs display
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except (OSError, ValueError) as exc:
            logger.warning("texture decode failed: %s", exc)
            return None
        arr = np.array(img, dtype=np.uint8)
        h, w = arr.shape[:2]
        tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, arr.tobytes(),
        )
        return tex

    def _invalidate_texture_cache(self) -> None:  # pragma: no cover - GL needs display
        if not self._texture_cache:
            return
        import contextlib
        with contextlib.suppress(Exception):
            glDeleteTextures(list(self._texture_cache.values()))
        self._texture_cache.clear()

    # ---- input ----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:   # pragma: no cover - Qt UI
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = _ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP
        self._apply_zoom(factor, event.position().x(), event.position().y())

    def mousePressEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_anchor = (event.position().x(), event.position().y())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if not self._panning:
            return
        dx = event.position().x() - self._pan_anchor[0]
        dy = event.position().y() - self._pan_anchor[1]
        self._pan_anchor = (event.position().x(), event.position().y())
        self._pan_x += dx
        self._pan_y += dy
        self._user_view_locked = True
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _apply_zoom(self, factor: float, sx: float, sy: float) -> None:   # pragma: no cover - Qt UI
        new_zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom * factor))
        actual = new_zoom / self._zoom
        # Anchor zoom on the cursor so the puppet under the mouse stays put.
        self._pan_x = sx - (sx - self._pan_x) * actual
        self._pan_y = sy - (sy - self._pan_y) * actual
        self._zoom = new_zoom
        self._user_view_locked = True
        self.zoom_changed.emit(self._zoom)
        self.update()
