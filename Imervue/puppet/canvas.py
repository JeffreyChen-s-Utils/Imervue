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
    GL_ALWAYS,
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_REPEAT,
    GL_COLOR_BUFFER_BIT,
    GL_DST_COLOR,
    GL_EQUAL,
    GL_FALSE,
    GL_FLOAT,
    GL_KEEP,
    GL_LINEAR,
    GL_LINE_LOOP,
    GL_ONE,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_REPLACE,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_STENCIL_BUFFER_BIT,
    GL_STENCIL_TEST,
    GL_TEXTURE_2D,
    GL_TEXTURE_COORD_ARRAY,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_TRUE,
    GL_UNSIGNED_BYTE,
    GL_UNSIGNED_INT,
    GL_VERTEX_ARRAY,
    glBegin,
    glBindTexture,
    glBlendFunc,
    glClear,
    glClearColor,
    glClearStencil,
    glColor4f,
    glColorMask,
    glDeleteTextures,
    glDisable,
    glDisableClientState,
    glDrawElements,
    glEnable,
    glEnableClientState,
    glEnd,
    glGenTextures,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glScalef,
    glStencilFunc,
    glStencilOp,
    glTexCoord2f,
    glTexCoordPointer,
    glTexImage2D,
    glTexParameteri,
    glTranslatef,
    glVertex2f,
    glVertexPointer,
    glViewport,
    GL_MODELVIEW,
    GL_PROJECTION,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.puppet.clip_masks import resolve_masks
from Imervue.puppet.document import PuppetDocument
from Imervue.puppet.hit_test import hit_test
from Imervue.puppet.render_prep import (
    DrawCommand,
    build_draw_list,
    fit_view,
)
from Imervue.puppet.mesh_edit import find_drawable_at, move_vertex
from Imervue.puppet.physics import PhysicsEngine
from Imervue.puppet.runtime import (
    apply_expressions,
    compose_all_drawables,
    default_parameter_values,
    resolve_drawable_color,
    resolve_drawable_opacity,
    resolve_part_state,
    resolve_pose_visibility,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent, QWheelEvent


logger = logging.getLogger("Imervue.plugin.puppet.canvas")

_ZOOM_STEP = 1.15
_MIN_ZOOM = 0.05
_MAX_ZOOM = 32.0
_CHECKER_TILE = 16


def _premultiply_alpha(rgba: np.ndarray) -> np.ndarray:
    """Return a copy of ``rgba`` (H × W × 4 uint8) with each colour
    channel pre-multiplied by alpha.

    Standard premultiplied-alpha conversion: ``RGB_pma = RGB * (A /
    255)``. Pixels with ``A = 0`` end up with ``RGB = 0`` regardless
    of their authored colour — which is exactly what kills the white
    halo that GL_LINEAR sampling otherwise drags out of transparent
    border pixels in Cubism atlases.

    Vectorised numpy so even a 4096² atlas premultiplies in a
    fraction of a second; pure helper so the test suite can verify
    behaviour without a GL context."""
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[-1] != 4:
        raise ValueError("expected H×W×4 uint8 RGBA array")
    alpha = rgba[..., 3:4].astype(np.uint16)
    rgb = rgba[..., :3].astype(np.uint16)
    # ``(rgb * alpha + 127) // 255`` rounds toward nearest, matching
    # the standard PMA rounding; plain ``// 255`` truncates and drifts
    # darker for mid-alpha pixels.
    rgb_pma = ((rgb * alpha + 127) // 255).astype(np.uint8)
    out = rgba.copy()
    out[..., :3] = rgb_pma
    return out


# Textures are uploaded **premultiplied** (RGB *= alpha) by
# ``_upload_texture`` so the blend functions below assume the source
# colour already carries its own alpha. The win: GL_LINEAR sampling
# across a mesh edge no longer leaks the texture's "background"
# colour into anti-aliased transparent pixels, which produced the
# visible white haloes on Cubism atlases (heel seam, dark_face
# overlay fade-in, etc.).
_BLEND_FUNCS = {
    "normal": (GL_ONE, GL_ONE_MINUS_SRC_ALPHA),
    "additive": (GL_ONE, GL_ONE),
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
    selection_cleared = Signal()
    """Emitted after a right-click drops the bone-selection overlay.
    The workspace wires this to ``BoneTreeDock.clear_selection`` so
    the tree row un-highlights alongside the canvas marker."""
    hit_area_triggered = Signal(str)
    """Emitted with the hit-area id when the user left-clicks inside
    one. Only fires when mesh-edit mode is off — when it's on, the
    left-click is consumed by the vertex drag instead."""

    def __init__(self, parent=None):
        # Request a stencil buffer so clip_mask drawing can use it.
        # Done before super().__init__() so the underlying GL surface
        # picks up the format on creation; Qt silently downgrades on
        # drivers that can't provide stencil, which is fine because
        # the stencil pass short-circuits when no drawable has a mask.
        fmt = QSurfaceFormat()
        fmt.setStencilBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)
        self.setFormat(fmt)
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
        self._part_opacity: dict[str, float] = {}
        self._drawable_opacity: dict[str, float] = {}
        self._drawable_tint: dict[str, tuple[float, float, float]] = {}
        # Editor selection — when the bone tree dock picks a deformer
        # we draw a highlight overlay so the user can see which one
        # they targeted without trying to interpret the canvas blind.
        self._selected_deformer: str | None = None
        self._physics = PhysicsEngine()
        self._physics_outputs: dict[str, float] = {}
        # Mesh-edit mode lets the user drag vertices; off by default.
        self._mesh_edit_enabled: bool = False
        self._mesh_edit_target: tuple[str, int] | None = None
        # The transparency-checker backdrop used to render as a grid of
        # immediate-mode quads — one per 16-pixel tile. On the March 7th
        # canvas (3503×7777) that's ~107k glBegin/glEnd cycles per frame
        # and the dominant playback bottleneck. Cache a 2×2 RGBA texture
        # once and tile it with GL_REPEAT instead.
        self._checker_texture: int | None = None
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
        self._physics.bind_document(document)
        self._physics_outputs = {}
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

    def set_parameter_values(self, values: dict[str, float]) -> None:
        """Batch-update many parameters in one go, recomputing the
        rig only once at the end. Big perf win for motion playback
        on Cubism-converted rigs where each frame writes 3+ tracks —
        per-call recompute was paying the full 307-drawable
        composition once per track instead of once per frame."""
        if self._document is None or not values:
            return
        changed = False
        for param_id, value in values.items():
            if param_id not in self._parameter_values:
                continue
            float_value = float(value)
            if self._parameter_values[param_id] != float_value:
                self._parameter_values[param_id] = float_value
                changed = True
        if not changed:
            return
        self._recompute_deformed_vertices()
        self.update()

    def force_parameter_values(self, values: dict[str, float]) -> None:
        """Batch-update parameters and recompute even when the values
        already match the cached state.

        Use case: a periodic driver (the auto-blink loop) needs to
        own the eye parameter every tick — without ``force``, another
        driver (motion player / webcam tracker) could write the same
        numeric value between blink ticks and the equality check
        below would skip the recompute, making the blink appear to
        stall after the first cycle."""
        if self._document is None or not values:
            return
        wrote_any = False
        for param_id, value in values.items():
            if param_id not in self._parameter_values:
                continue
            self._parameter_values[param_id] = float(value)
            wrote_any = True
        if not wrote_any:
            return
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

    def selected_deformer(self) -> str | None:
        return self._selected_deformer

    def set_selected_deformer(self, deformer_id: str | None) -> None:
        """Pick which deformer the editor wants highlighted on canvas.
        The selection overlay draws an anchor marker plus a bounding
        box around the targeted drawables so the user can see what
        the bone tree click referred to. An empty string is treated
        the same as ``None`` so callers that pump signal payloads
        through can clear via either spelling."""
        new_value = (
            deformer_id if isinstance(deformer_id, str) and deformer_id else None
        )
        if new_value == self._selected_deformer:
            return
        self._selected_deformer = new_value
        self.update()

    def clear_selection(self) -> None:
        """Drop the selection overlay. Convenience wrapper used by the
        right-click clear path; equivalent to ``set_selected_deformer(None)``
        followed by emitting :attr:`selection_cleared`."""
        if self._selected_deformer is None:
            return
        self._selected_deformer = None
        self.update()
        self.selection_cleared.emit()

    def _recompute_deformed_vertices(self) -> None:
        if self._document is None:
            self._deformed_vertices = {}
            self._visibility = {}
            self._part_opacity = {}
            self._drawable_opacity = {}
            self._drawable_tint = {}
            return
        active_values = apply_expressions(
            self._parameter_values, self._active_expressions,
        )
        # Physics outputs are layered last so an authored slider /
        # motion / expression still wins where they explicitly set
        # the same parameter, but the physics rig drives whichever
        # parameter the rig nominated.
        active_values = {**active_values, **self._physics_outputs}
        if active_values:
            self._deformed_vertices = compose_all_drawables(
                self._document, active_values,
            )
        else:
            self._deformed_vertices = {}
        # Pose visibility applies even when there are no parameters —
        # users may have a static rig with weapon-swap pose groups.
        pose_visibility = resolve_pose_visibility(
            self._document, self._active_pose,
        )
        # Layer the Part tree's cascading visibility/opacity on top.
        # The renderer reads ``self._visibility`` and the per-drawable
        # opacity, so we fold Part visibility AND with pose visibility
        # and cache the part-opacity multiplier separately.
        part_state = resolve_part_state(self._document)
        merged_visibility: dict[str, bool] = {}
        merged_opacity: dict[str, float] = {}
        for drawable in self._document.drawables:
            pose_vis = pose_visibility.get(drawable.id, bool(drawable.visible))
            part_vis, part_op = part_state.get(drawable.id, (True, 1.0))
            merged_visibility[drawable.id] = pose_vis and part_vis
            merged_opacity[drawable.id] = part_op
        self._visibility = merged_visibility
        self._part_opacity = merged_opacity
        # Pre-compute the per-drawable multiply tint and parameter-driven
        # alpha so paintGL just reads them without rerunning the curves
        # per frame. ``resolve_drawable_opacity`` folds the authored
        # base opacity with every ``opacity_keys`` curve — that's what
        # lets a hidden alternate-pose mesh fade in when its driving
        # parameter (e.g. a wave gesture) fires.
        self._drawable_opacity = {
            drawable.id: resolve_drawable_opacity(drawable, active_values)
            for drawable in self._document.drawables
        }
        self._drawable_tint = {
            drawable.id: resolve_drawable_color(drawable, active_values)
            for drawable in self._document.drawables
        }

    def step_physics(self, dt: float) -> None:
        """Advance the physics chains by ``dt`` seconds and re-fold
        their outputs into the deformed-vertex cache. Workspace's
        frame timer calls this once per tick."""
        if self._document is None:
            return
        active_values = apply_expressions(
            self._parameter_values, self._active_expressions,
        )
        self._physics_outputs = self._physics.step(dt, active_values)
        self._recompute_deformed_vertices()
        self.update()

    def physics(self) -> PhysicsEngine:
        return self._physics

    # ---- mesh-edit mode --------------------------------------------------

    def set_mesh_edit_enabled(self, enabled: bool) -> None:
        """Toggle the click-to-drag vertex editor. Switching off also
        clears any active drag target."""
        self._mesh_edit_enabled = bool(enabled)
        if not enabled:
            self._mesh_edit_target = None

    def mesh_edit_enabled(self) -> bool:
        return self._mesh_edit_enabled

    def begin_mesh_edit_at(self, image_x: float, image_y: float) -> bool:
        """Pick the topmost vertex within the snap radius of ``(image_x,
        image_y)`` and start a drag. Returns ``True`` if a vertex was
        grabbed."""
        if not self._mesh_edit_enabled or self._document is None:
            return False
        hit = find_drawable_at(self._document, image_x, image_y)
        self._mesh_edit_target = hit
        return hit is not None

    def update_mesh_edit_drag(self, image_x: float, image_y: float) -> bool:
        """Move the grabbed vertex to ``(image_x, image_y)`` and rebuild
        the draw list so the renderer picks up the change."""
        if not self._mesh_edit_enabled or self._mesh_edit_target is None:
            return False
        if self._document is None:
            return False
        drawable_id, vertex_idx = self._mesh_edit_target
        drawable = self._document.drawable(drawable_id)
        if drawable is None:
            return False
        if not move_vertex(drawable, vertex_idx, image_x, image_y):
            return False
        self._draw_list = build_draw_list(self._document)
        self._recompute_deformed_vertices()
        self.update()
        return True

    def end_mesh_edit_drag(self) -> None:
        self._mesh_edit_target = None

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
        self._draw_selection_overlay()
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
        """Draw the checker backdrop as one repeating-textured quad.

        The old immediate-mode grid hit ~107k glBegin/glEnd cycles per
        frame on the March 7th canvas (3503×7777 / 16-pixel tile). Now
        the canvas-wide quad samples a cached 2×2 RGBA texture with
        ``GL_REPEAT``, so the entire backdrop is one draw call no
        matter how large the rig."""
        if self._document is None:
            return
        w, h = self._document.size
        tex_id = self._ensure_checker_texture()
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Each texel covers one tile; tile_size pixels per texel gives
        # the visible checker scale.
        u_repeat = w / (2.0 * _CHECKER_TILE)
        v_repeat = h / (2.0 * _CHECKER_TILE)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0)
        glVertex2f(0.0, 0.0)
        glTexCoord2f(u_repeat, 0.0)
        glVertex2f(w, 0.0)
        glTexCoord2f(u_repeat, v_repeat)
        glVertex2f(w, h)
        glTexCoord2f(0.0, v_repeat)
        glVertex2f(0.0, h)
        glEnd()

    def _ensure_checker_texture(self) -> int:  # pragma: no cover - GL needs display
        """Lazy-build a 2×2 RGBA texture carrying the checker pattern.

        Stored on the canvas, kept across document swaps (the pattern
        is document-independent). Wrap mode is ``GL_REPEAT`` so the
        backdrop quad can tile it across an arbitrarily-sized canvas
        in one draw call. Filter mode is ``GL_NEAREST`` so the tiles
        stay crisp at any zoom."""
        if self._checker_texture is not None:
            return self._checker_texture
        from OpenGL.GL import GL_NEAREST
        dark = (33, 33, 38, 255)
        light = (46, 46, 51, 255)
        pixels = np.array(
            [[dark, light], [light, dark]], dtype=np.uint8,
        )
        tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            2, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.tobytes(),
        )
        self._checker_texture = tex
        return tex

    def _draw_drawables(self) -> None:  # pragma: no cover - GL needs display
        masks = resolve_masks(self._draw_list)
        for cmd in self._draw_list:
            visible = self._visibility.get(cmd.drawable_id, cmd.visible)
            if not visible:
                continue
            tex_id = self._texture_for(cmd.texture)
            if tex_id is None:
                continue
            sfactor, dfactor = _BLEND_FUNCS.get(cmd.blend_mode, _BLEND_FUNCS["normal"])
            glBlendFunc(sfactor, dfactor)
            # ``_drawable_opacity`` folds ``cmd.opacity`` with parameter-
            # driven ``opacity_keys`` curves; ``_part_opacity`` carries
            # the cascading Part-tree multiplier on top.
            effective_opacity = self._drawable_opacity.get(
                cmd.drawable_id, cmd.opacity,
            ) * self._part_opacity.get(cmd.drawable_id, 1.0)
            tint_r, tint_g, tint_b = self._drawable_tint.get(
                cmd.drawable_id, (1.0, 1.0, 1.0),
            )
            # Premultiply the vertex tint by the opacity so a partly-
            # faded drawable doesn't over-brighten when the GL pipeline
            # modulates the (already-premultiplied) texture RGB.
            glColor4f(
                tint_r * effective_opacity,
                tint_g * effective_opacity,
                tint_b * effective_opacity,
                effective_opacity,
            )
            glBindTexture(GL_TEXTURE_2D, tex_id)
            verts = self._deformed_vertices.get(cmd.drawable_id, cmd.vertices)
            mask_cmd = masks.get(cmd.drawable_id)
            if mask_cmd is None:
                self._draw_indexed(verts, cmd.uvs, cmd.indices)
                continue
            self._draw_with_stencil(mask_cmd, verts, cmd.uvs, cmd.indices)

    def _draw_with_stencil(  # pragma: no cover - GL needs display
        self, mask_cmd, verts, uvs, indices,
    ) -> None:
        """Render ``verts/uvs/indices`` clipped to ``mask_cmd``'s shape
        using the stencil buffer. The mask drawable's deformed vertices
        are used (so a hair mask follows the head's deformation), and
        the stencil buffer is wiped at the end so the next clipped pair
        starts clean."""
        mask_verts = self._deformed_vertices.get(
            mask_cmd.drawable_id, mask_cmd.vertices,
        )
        glEnable(GL_STENCIL_TEST)
        glClearStencil(0)
        glClear(GL_STENCIL_BUFFER_BIT)
        # Stencil-only pass — write 1 wherever the mask drew. Disable
        # color writes so the mask shape doesn't appear on screen here;
        # its own pass in the main loop is responsible for showing it.
        glStencilFunc(GL_ALWAYS, 1, 0xFF)
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE)
        glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE)
        self._draw_indexed(mask_verts, mask_cmd.uvs, mask_cmd.indices)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        # Target draws only where stencil == 1.
        glStencilFunc(GL_EQUAL, 1, 0xFF)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        self._draw_indexed(verts, uvs, indices)
        glDisable(GL_STENCIL_TEST)

    def _draw_selection_overlay(self) -> None:   # pragma: no cover - GL needs display
        """If a bone-tree row is selected, draw a marker so the user
        can see which deformer the dock referred to. Two pieces:

        * Yellow ring at the deformer's anchor (rotation only — warp
          deformers have no single anchor; their grid bounds become
          the bbox below).
        * Yellow bounding rectangle around the union of the
          deformer's target drawables (using their *deformed* vertex
          positions, so the box follows the live rig).
        """
        if self._document is None or self._selected_deformer is None:
            return
        deformer = self._document.deformer(self._selected_deformer)
        if deformer is None:
            return
        bbox = self._selection_bbox(deformer)
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 0.92, 0.20, 0.85)
        if bbox is not None:
            x0, y0, x1, y1 = bbox
            glBegin(GL_LINE_LOOP)
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
            glEnd()
        anchor = deformer.form.get("anchor") if deformer.type == "rotation" else None
        if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
            self._draw_anchor_ring(float(anchor[0]), float(anchor[1]))
        glEnable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)

    def _selection_bbox(   # pragma: no cover - GL needs display
        self, deformer,
    ) -> tuple[float, float, float, float] | None:
        if self._document is None:
            return None
        xs: list[float] = []
        ys: list[float] = []
        for drawable_id in deformer.drawables:
            drawable = self._document.drawable(drawable_id)
            if drawable is None:
                continue
            verts = self._deformed_vertices.get(drawable.id)
            if verts is None or len(verts) == 0:
                if not drawable.vertices:
                    continue
                arr = np.asarray(drawable.vertices, dtype=np.float64)
            else:
                arr = np.asarray(verts, dtype=np.float64).reshape(-1, 2)
            if arr.size == 0:
                continue
            xs.append(float(arr[:, 0].min()))
            xs.append(float(arr[:, 0].max()))
            ys.append(float(arr[:, 1].min()))
            ys.append(float(arr[:, 1].max()))
        if not xs or not ys:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def _draw_anchor_ring(  # pragma: no cover - GL needs display
        self, ax: float, ay: float,
    ) -> None:
        import math as _math
        segments = 24
        radius = 8.0 / max(self._zoom, 0.05)
        glBegin(GL_LINE_LOOP)
        for i in range(segments):
            theta = 2.0 * _math.pi * i / segments
            glVertex2f(ax + radius * _math.cos(theta), ay + radius * _math.sin(theta))
        glEnd()

    @staticmethod
    def _draw_indexed(  # pragma: no cover - GL needs display
        vertices: np.ndarray, uvs: np.ndarray, indices: np.ndarray,
    ) -> None:
        """Submit one triangle list to the fixed-function pipeline using
        client-side vertex arrays.

        Per-vertex ``glBegin/glVertex2f`` runs in the millions for the
        March 7th rig (307 drawables × ~200 verts × 60 fps) and was the
        playback-lag bottleneck. ``glDrawElements`` with the same
        numpy arrays drops paint cost ~10-50× by pushing the per-vertex
        loop into the GL driver."""
        verts32 = np.ascontiguousarray(vertices, dtype=np.float32)
        uvs32 = np.ascontiguousarray(uvs, dtype=np.float32)
        idx32 = np.ascontiguousarray(indices, dtype=np.uint32)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glVertexPointer(2, GL_FLOAT, 0, verts32)
        glTexCoordPointer(2, GL_FLOAT, 0, uvs32)
        glDrawElements(GL_TRIANGLES, int(idx32.size), GL_UNSIGNED_INT, idx32)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

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

    # pragma: no cover - GL needs display
    def _upload_texture(self, png_bytes: bytes) -> int | None:
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except (OSError, ValueError) as exc:
            logger.warning("texture decode failed: %s", exc)
            return None
        arr = np.array(img, dtype=np.uint8)
        # Premultiply RGB by alpha so GL_LINEAR sampling at mesh edges
        # interpolates "half-transparent content" rather than "content
        # blended with the texture's white background". Without this,
        # Cubism atlas drawables produced a visible white halo at every
        # anti-aliased edge — most obvious on the heel seam and the
        # dark_face overlay during its alpha fade-in.
        arr = _premultiply_alpha(arr)
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
            return
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click anywhere on the canvas clears the bone
            # selection overlay. Cheap shortcut for the user — the
            # tree dock's row picks up the deselect through the
            # ``selection_cleared`` signal.
            self.clear_selection()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        ix, iy = self._screen_to_image(
            event.position().x(), event.position().y(),
        )
        if self._mesh_edit_enabled:
            self.begin_mesh_edit_at(ix, iy)
            return
        self.try_trigger_hit_area_at(ix, iy)

    def try_trigger_hit_area_at(self, image_x: float, image_y: float) -> str | None:
        """Run hit-testing at ``(image_x, image_y)`` and, if a hit area
        contains the point, emit :attr:`hit_area_triggered`. Returns the
        triggered id (or ``None``) so callers can act without going
        through the signal. Exposed as a method so tests can exercise
        the hit path without a real Qt mouse event."""
        if self._document is None or not self._document.hit_areas:
            return None
        hit = hit_test(
            self._document, image_x, image_y,
            deformed_vertices=self._deformed_vertices or None,
        )
        if hit is not None:
            self.hit_area_triggered.emit(hit)
        return hit

    def mouseMoveEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if self._panning:
            dx = event.position().x() - self._pan_anchor[0]
            dy = event.position().y() - self._pan_anchor[1]
            self._pan_anchor = (event.position().x(), event.position().y())
            self._pan_x += dx
            self._pan_y += dy
            self._user_view_locked = True
            self.update()
            return
        if self._mesh_edit_enabled and self._mesh_edit_target is not None:
            ix, iy = self._screen_to_image(
                event.position().x(), event.position().y(),
            )
            self.update_mesh_edit_drag(ix, iy)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:   # pragma: no cover - Qt UI
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self._mesh_edit_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.end_mesh_edit_drag()

    # pragma: no cover - Qt UI
    def _screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom == 0:
            return 0.0, 0.0
        return (sx - self._pan_x) / self._zoom, (sy - self._pan_y) / self._zoom

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
