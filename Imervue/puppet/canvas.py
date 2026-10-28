"""Puppet GL widget identity, signals and per-instance state.

Domain mixins own rig evaluation, editing, input and frame lifecycles.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from Imervue.puppet.document import PuppetDocument
from Imervue.puppet.render_prep import DrawCommand
from Imervue.puppet.physics import PhysicsEngine
from Imervue.puppet.canvas_render import PuppetCanvasRenderMixin
from Imervue.puppet.canvas_gl_state import (
    _preserved_gl_render_state,
    offscreen_framebuffer_format,
)
from Imervue.puppet.canvas_view import _fit_scale_and_pan
from Imervue.puppet.canvas_physics import (
    time,
    _outputs_close,
    _PHYSICS_INTERVAL_MS,
    _PHYSICS_STEP,
    _PHYSICS_MAX_DT,
    _PHYSICS_REDRAW_THRESHOLD,
)
from Imervue.puppet.canvas_parameters import PuppetCanvasParametersMixin
from Imervue.puppet.canvas_rig import PuppetCanvasRigMixin
from Imervue.puppet.canvas_physics import PuppetCanvasPhysicsMixin
from Imervue.puppet.canvas_overrides import PuppetCanvasOverridesMixin
from Imervue.puppet.canvas_editing import PuppetCanvasEditingMixin
from Imervue.puppet.canvas_view import PuppetCanvasViewMixin
from Imervue.puppet.canvas_pointer import PuppetCanvasPointerMixin
from Imervue.puppet.canvas_frame import PuppetCanvasFrameMixin

__all__ = [
    "PuppetCanvas", "offscreen_framebuffer_format", "_preserved_gl_render_state",
    "_fit_scale_and_pan", "_outputs_close", "_PHYSICS_STEP", "_PHYSICS_MAX_DT",
    "_PHYSICS_REDRAW_THRESHOLD", "time",
]


class PuppetCanvas(
    PuppetCanvasParametersMixin,
    PuppetCanvasRigMixin,
    PuppetCanvasPhysicsMixin,
    PuppetCanvasOverridesMixin,
    PuppetCanvasEditingMixin,
    PuppetCanvasViewMixin,
    PuppetCanvasPointerMixin,
    PuppetCanvasFrameMixin,
    PuppetCanvasRenderMixin,
    QOpenGLWidget,
):
    """Render and interact with one deformable puppet document at a time."""

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
        self._physics_lag = 0.0
        # Mesh-edit mode lets the user drag vertices; off by default.
        self._mesh_edit_enabled: bool = False
        self._mesh_edit_target: tuple[str, int] | None = None

    def _init_gl_caches(self) -> None:
        """GL resources created lazily on first paint: checker, pet shadow, VBOs."""
        # The transparency-checker backdrop used to render as a grid of
        # immediate-mode quads — one per 16-pixel tile. On a large imported
        # Cubism canvas (3503×7777) that's ~107k glBegin/glEnd cycles per frame
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
