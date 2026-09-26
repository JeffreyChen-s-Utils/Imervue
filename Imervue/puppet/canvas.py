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

import contextlib
import time
from typing import TYPE_CHECKING

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_TEXTURE_2D,
    glClear,
    glClearColor,
    glEnable,
    glGetFloatv,
    glGetIntegerv,
    glLoadIdentity,
    glMatrixMode,
    glOrtho,
    glPopMatrix,
    glPushMatrix,
    glScalef,
    glTranslatef,
    glViewport,
    GL_COLOR_CLEAR_VALUE,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_VIEWPORT,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

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
from Imervue.puppet.canvas_render import PuppetCanvasRenderMixin

if TYPE_CHECKING:
    from PySide6.QtGui import QImage, QMouseEvent, QWheelEvent


_ZOOM_STEP = 1.15
_MIN_ZOOM = 0.05
_MAX_ZOOM = 32.0


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


def _fit_scale_and_pan(
    doc_size: tuple[float, float], width: int, height: int,
) -> tuple[float, float, float] | None:
    """``(scale, pan_x, pan_y)`` fitting ``doc_size`` into ``width`` x ``height``.

    Keeps the aspect ratio and centres the document, so the whole canvas
    lands inside the target with no cropping. ``None`` when the document has
    no area.
    """
    doc_w, doc_h = doc_size
    if doc_w <= 0 or doc_h <= 0:
        return None
    scale = min(width / doc_w, height / doc_h)
    return scale, (width - doc_w * scale) / 2.0, (height - doc_h * scale) / 2.0

# The physics chains' own clock: motions, drivers and the pet's paint tick only
# move the parameters that feed the chains. About 60 steps a second while a
# shown rig has chains; a stalled frame integrates as at most 50 ms, and an
# output change below the threshold is not redrawn, so a settled rig costs a
# step (under a millisecond for the bundled rigs) and no repaint.
_PHYSICS_INTERVAL_MS = 16
_PHYSICS_MAX_DT = 0.05
_PHYSICS_REDRAW_THRESHOLD = 1e-4


def _outputs_close(new: dict[str, float], old: dict[str, float]) -> bool:
    """Whether two physics output maps differ by less than the redraw threshold."""
    return new.keys() == old.keys() and all(
        abs(value - old[key]) < _PHYSICS_REDRAW_THRESHOLD for key, value in new.items())


class PuppetCanvas(PuppetCanvasRenderMixin, QOpenGLWidget):
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
    cursor_moved = Signal(float, float)
    """Image-space pointer position as it moves over the canvas (not while
    panning or dragging a mesh vertex); InputEngine turns it into the
    Drag-track head look-at."""
    pose_changed = Signal(str, str)
    """``(group_id, drawable_id)`` after :meth:`set_pose_active` shows a member."""

    def __init__(self, parent=None, *, pet_mode: bool = False):
        # Request a stencil buffer so clip_mask drawing can use it.
        # Done before super().__init__() so the underlying GL surface
        # picks up the format on creation; Qt silently downgrades on
        # drivers that can't provide stencil, which is fine because
        # the stencil pass short-circuits when no drawable has a mask.
        #
        # ``pet_mode`` switches the canvas into the desktop-pet
        # rendering profile: the checker backdrop is suppressed and
        # ``paintGL`` clears to fully-transparent so the host window
        # (which has ``WA_TranslucentBackground`` set) shows the
        # desktop through every pixel the puppet doesn't draw. An
        # 8-bit alpha buffer is requested in the surface format so
        # the framebuffer can actually carry that transparency — the
        # default GL widget allocates RGB only.
        fmt = self._surface_format(pet_mode)
        # Make ``fmt`` the process default only for the duration of surface
        # creation, then restore the previous default. Leaving it set globally
        # perturbed the format inherited by every GL widget constructed after
        # this canvas (e.g. the main image viewer gained a stray stencil/alpha
        # buffer depending on construction order). ``setFormat`` below is what
        # actually binds the format to this widget.
        prev_default = QSurfaceFormat.defaultFormat()
        QSurfaceFormat.setDefaultFormat(fmt)
        try:
            super().__init__(parent)
            self.setFormat(fmt)
        finally:
            QSurfaceFormat.setDefaultFormat(prev_default)
        self._pet_mode = bool(pet_mode)
        if pet_mode:
            self._apply_pet_translucency()
        self._init_document_state()
        self._init_view_state()
        self._init_rig_state()
        self._init_editor_state()
        self._init_gl_caches()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @staticmethod
    def _surface_format(pet_mode: bool) -> QSurfaceFormat:
        """Stencil for clip masks; pet mode adds an 8-bit alpha buffer for transparency."""
        fmt = QSurfaceFormat()
        fmt.setStencilBufferSize(8)
        if pet_mode:
            fmt.setAlphaBufferSize(8)
        return fmt

    def _apply_pet_translucency(self) -> None:
        """Let the desktop show through every pixel the puppet doesn't draw.

        The host PetWindow has WA_TranslucentBackground set, but Qt would
        still paint a system-coloured background behind the GL widget before
        it renders — leaving an opaque rectangle around the puppet on the
        desktop. Mirror the translucency attributes onto the canvas itself so
        no opaque background paint runs, then make the GL widget stack on top
        of any sibling so the window-composite step honours its per-pixel alpha.
        """
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)

    def _init_document_state(self) -> None:
        """Document, draw list and the per-document texture cache."""
        self._document: PuppetDocument | None = None
        self._draw_list: list[DrawCommand] = []
        self._texture_cache: dict[str, int] = {}

    def _init_view_state(self) -> None:
        """Zoom / pan and the panning gesture state."""
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._user_view_locked: bool = False
        self._panning: bool = False
        self._pan_anchor: tuple[float, float] = (0.0, 0.0)

    def _init_rig_state(self) -> None:
        """Parameter values, expressions, pose groups and per-drawable render overrides."""
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

    def _init_editor_state(self) -> None:
        """Deformer selection, physics and mesh-edit state."""
        # Editor selection — when the bone tree dock picks a deformer
        # we draw a highlight overlay so the user can see which one
        # they targeted without trying to interpret the canvas blind.
        self._selected_deformer: str | None = None
        self._physics = PhysicsEngine()
        self._physics_outputs: dict[str, float] = {}
        self._physics_timer = QTimer(self)
        self._physics_timer.setInterval(_PHYSICS_INTERVAL_MS)
        self._physics_timer.timeout.connect(self._on_physics_tick)
        self._physics_clock: float | None = None
        # Mesh-edit mode lets the user drag vertices; off by default.
        self._mesh_edit_enabled: bool = False
        self._mesh_edit_target: tuple[str, int] | None = None

    def _init_gl_caches(self) -> None:
        """GL resources created lazily on first paint: checker, pet shadow, VBOs."""
        # The transparency-checker backdrop used to render as a grid of
        # immediate-mode quads — one per 16-pixel tile. On the March 7th
        # canvas (3503×7777) that's ~107k glBegin/glEnd cycles per frame
        # and the dominant playback bottleneck. Cache a 2×2 RGBA texture
        # once and tile it with GL_REPEAT instead.
        self._checker_texture: int | None = None
        # Pet-mode drop shadow: a small radial-gradient RGBA
        # texture stretched to a flattened ellipse below the rig.
        # State is canvas-local (per-instance) so multi-pet setups
        # can have one pet with shadow on, another off.
        self._pet_shadow_texture: int | None = None
        self._pet_shadow_enabled: bool = False
        self._pet_shadow_opacity: float = 1.0
        self._pet_shadow_scale: float = 1.0
        # Per-drawable VBO cache. Each entry holds
        # ``{vert_vbo, uv_vbo, idx_ibo, idx_count, vert_bytes}`` so the
        # immutable UV + index arrays live on the GPU once per document
        # while the per-frame deformed vertices upload via
        # ``glBufferSubData`` (or full ``glBufferData`` when mesh edit
        # changed the vertex count). Invalidated on document swap; the
        # next paint lazily recreates the buffers for each drawable.
        self._drawable_buffers: dict[str, dict] = {}

    # ---- public API -----------------------------------------------------

    def _current_gl_context(self):
        """Current this widget's GL context for texture/buffer frees issued
        outside ``paintGL`` (document swap runs from file-open / undo / a network
        or timer callback), so ``glDelete*`` isn't dropped and the resource
        leaked."""
        from Imervue.gpu_image_view.gl_context import make_current_guard
        return make_current_guard(self)

    def load_document(self, document: PuppetDocument | None) -> None:
        """Bind ``document`` to the canvas. Pass ``None`` to clear.

        Texture cache is invalidated on every document swap; the next
        ``paintGL`` re-uploads everything against the bound document's
        ``textures`` map. Parameter values reset to each parameter's
        ``default``.
        """
        self._document = document
        self._draw_list = build_draw_list(document) if document is not None else []
        # Frees run off paintGL (file-open / undo / pet rig swap) — need a
        # current GL context or the textures/VBOs leak on every reload.
        with self._current_gl_context():
            self._invalidate_texture_cache()
            self._invalidate_buffer_cache()
        self._user_view_locked = False
        self._parameter_values = (
            default_parameter_values(document) if document is not None else {}
        )
        self._active_expressions = []
        self._active_pose = {}
        self._physics.bind_document(document)
        self._physics_outputs = {}
        self._sync_physics_timer()
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
        their outputs into the deformed-vertex cache.

        The canvas's own physics clock calls this (see
        :meth:`_sync_physics_timer`). Outputs that moved less than the
        redraw threshold leave the vertices and the frame alone.
        """
        if self._document is None:
            return
        active_values = apply_expressions(
            self._parameter_values, self._active_expressions,
        )
        outputs = self._physics.step(dt, active_values)
        if _outputs_close(outputs, self._physics_outputs):
            return
        self._physics_outputs = outputs
        self._recompute_deformed_vertices()
        self.update()

    def reset_physics(self) -> None:
        """Snap every physics chain back to rest and drop its outputs."""
        self._physics.reset()
        self._physics_outputs = {}
        self._recompute_deformed_vertices()
        self.update()

    def _sync_physics_timer(self) -> None:
        """Run the physics clock only while a shown rig has physics chains."""
        wanted = bool(self._physics.chain_ids()) and self.isVisible()
        if wanted == self._physics_timer.isActive():
            return
        if wanted:
            self._physics_clock = None
            self._physics_timer.start()
        else:
            self._physics_timer.stop()

    def _on_physics_tick(self) -> None:
        """Step the chains by the real time since the last tick, capped."""
        now = time.monotonic()
        last, self._physics_clock = self._physics_clock, now
        if last is not None:
            self.step_physics(min(now - last, _PHYSICS_MAX_DT))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._sync_physics_timer()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().hideEvent(event)
        self._sync_physics_timer()

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
        self.pose_changed.emit(group_id, drawable_id)
        return True

    def active_pose(self) -> dict[str, str]:
        return dict(self._active_pose)

    def visibility(self) -> dict[str, bool]:
        return dict(self._visibility)

    # ---- GL lifecycle ---------------------------------------------------

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
        if not self._pet_mode:
            self._draw_transparency_backdrop()
        if self._pet_mode and self._pet_shadow_enabled:
            self._draw_pet_shadow()
        self._draw_drawables()
        if not self._pet_mode:
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
        from PySide6.QtOpenGL import (
            QOpenGLFramebufferObject,
            QOpenGLFramebufferObjectFormat,
        )

        self.makeCurrent()
        fbo = None
        try:
            fmt = QOpenGLFramebufferObjectFormat()
            fbo = QOpenGLFramebufferObject(width, height, fmt)
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

    # ---- pet-mode drop shadow ------------------------------------------

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

    # ---- texture cache --------------------------------------------------


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
        ix, iy = self._screen_to_image(
            event.position().x(), event.position().y(),
        )
        if self._mesh_edit_enabled and self._mesh_edit_target is not None:
            self.update_mesh_edit_drag(ix, iy)
            return
        self.cursor_moved.emit(ix, iy)

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
