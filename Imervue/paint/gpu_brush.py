"""GPU-accelerated dab rasterisation via OpenGL FBO + GLSL shader.

Wired into the live brush flow through
:mod:`Imervue.paint.tool_dispatcher`: a single un-mirrored brush
stroke whose options pass :func:`_gpu_supported` runs every dab
through a :class:`GPUDabSession` instead of through
:func:`Imervue.paint.brush_engine.apply_dab`. Symmetry strokes
(``mirror`` count > 1) stay on the CPU because each per-stroke FBO
can't see its siblings' updates without an expensive per-extend
re-upload.

Live-paint visibility is preserved by the per-extend readback:

1. :class:`PaintCanvas._dispatch_pointer` makes the widget's GL
   context current before calling the dispatcher (Qt only
   auto-binds during ``paintGL`` / ``resizeGL``).
2. The dispatcher creates a :class:`GPUBrushStroke` via
   :func:`make_brush_stroke`; ``begin`` uploads the layer to a
   freshly created FBO + texture and stamps the first dab.
3. Each ``begin`` / ``extend`` / ``end`` ends with
   ``glReadPixels`` copying the FBO back into the layer numpy
   in-place — the next ``paintGL`` therefore composites a layer
   that already includes the new dabs.
4. ``end`` releases every GL object and restores the prior FBO /
   viewport that ``paintGL`` itself depends on.

Constants:

1. :class:`GPUDabSession` — owns the FBO + textures for a stroke.
   ``__init__`` uploads the layer; ``stamp`` renders one dab via
   shader; ``read_back`` issues ``glReadPixels`` to sync the layer
   numpy in-place; ``dispose`` frees the GL objects and restores
   prior FBO / viewport.
2. :class:`GPUBrushStroke` — drop-in subclass of the CPU
   :class:`BrushStroke` that overrides ``_paint_dab`` to redirect
   each stamp onto a :class:`GPUDabSession`. Same begin / extend /
   end / stroke_damage interface; same taper / kernel restyling
   support inherited from the base class.
3. :func:`make_brush_stroke` — factory that returns the GPU stroke
   when GL is available, the options are GPU-compatible, and the
   caller passes ``prefer_gpu=True``. Otherwise it returns the
   CPU :class:`BrushStroke` so behaviour is identical to the
   pre-GPU path.

Compatibility gate — :func:`_gpu_supported` reports False for:

* a non-``normal`` blend mode (only ``GL_SRC_ALPHA``-based alpha-over
  is wired up; full Photoshop blend modes need per-mode shaders),
* a selection mask (would require a second texture sample + multiply
  in the shader; deferred),
* pixel-art snapping (the integer-snap rule lives in the CPU stroke
  state machine; not worth duplicating in GLSL),
* per-dab kernel restyling (``pencil`` / ``airbrush``) — re-uploading
  a kernel texture every dab erases the GPU win.

Coordinate convention matches the rest of the paint workspace:
canvas is Y-down (``glOrtho(0, w, h, 0, ...)``), so canvas pixel
``(cx, cy)`` from the brush engine maps to the exact same position
on the FBO with no axis flip. The texture upload and
``glReadPixels`` round-trip are byte-for-byte symmetric.

GL paths in this module are marked ``# pragma: no cover - GL needs
display server`` because the test runner has no live GL context;
shader-helper logic that does not touch GL (matrix math, support
predicates, factory dispatch with stub sessions) is exercised in
:mod:`tests.test_paint_gpu_brush`.
"""
from __future__ import annotations

import ctypes
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.paint.gpu_brush")

_VERTEX_SHADER = """\
#version 120
attribute vec2 a_position;
attribute vec2 a_texcoord;
varying vec2 v_texcoord;
uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
    v_texcoord = a_texcoord;
}
"""

_FRAGMENT_SHADER = """\
#version 120
varying vec2 v_texcoord;
uniform sampler2D u_kernel;
uniform vec3 u_color;
uniform float u_opacity;

void main() {
    float k = texture2D(u_kernel, v_texcoord).r;
    float a = clamp(k * u_opacity, 0.0, 1.0);
    gl_FragColor = vec4(u_color, a);
}
"""


# Compiled shader cached per QOpenGLContext id so a re-used context
# doesn't pay the ~5ms compile cost on every stroke.
@dataclass
class _ShaderProgram:
    """Resolved attribute / uniform locations for the dab shader."""

    program: int
    a_position: int
    a_texcoord: int
    u_mvp: int
    u_kernel: int
    u_color: int
    u_opacity: int


# Compiled shader cached per QOpenGLContext id so a re-used context
# doesn't pay the ~5ms compile cost on every stroke.
_PROGRAM_CACHE: dict[int, _ShaderProgram] = {}


def _ortho(left: float, right: float, bottom: float, top: float) -> np.ndarray:
    """Build a 4x4 orthographic projection (column-major float32).

    Pure math, GL-free — exposed at module scope so the unit tests
    can exercise the matrix without spinning up a GL context.
    Calling with ``bottom > top`` produces the Y-down ortho the
    paint workspace uses everywhere else.
    """
    near, far = -1.0, 1.0
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[3, 0] = -(right + left) / (right - left)
    m[3, 1] = -(top + bottom) / (top - bottom)
    m[3, 2] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


# Set True only when :class:`PaintCanvas` has explicitly bound its
# context for a dispatcher call. ``QOpenGLContext.currentContext()``
# alone is unreliable in tests because a previously instantiated
# widget can leave a stale context bound to the thread; trying to
# render onto that stale binding silently produces wrong results
# instead of raising. The canvas widget owns the lifecycle and
# flips this flag inside its ``makeCurrent`` / ``doneCurrent``
# bracket — see ``Imervue/paint/canvas.py``.
_gpu_session_active = False


def set_gpu_session_active(active: bool) -> None:
    """Mark the current call-stack as inside a fresh ``makeCurrent`` block.

    The Paint workspace's canvas calls this with ``True`` before
    dispatching a pointer event and ``False`` after; the brush
    factory consults the flag (via :func:`gpu_available`) to decide
    whether the GPU stamp path is safe to use. Callers outside the
    canvas (unit tests that drive the dispatcher directly) should
    not toggle this — they get the CPU stroke automatically.
    """
    global _gpu_session_active
    _gpu_session_active = bool(active)


def gpu_available() -> bool:
    """Return ``True`` when a fresh GL context is bound for rendering.

    Two gates: the canvas-managed :data:`_gpu_session_active` flag
    (see :func:`set_gpu_session_active`) AND a real
    ``QOpenGLContext.currentContext()`` probe. Both must hold;
    either failing routes the brush back to the CPU stroke.
    """
    if not _gpu_session_active:
        return False
    try:
        from PySide6.QtGui import QOpenGLContext
    except ImportError:   # pragma: no cover - PySide6 always present at runtime
        return False
    return QOpenGLContext.currentContext() is not None


def _gpu_supported(options) -> bool:
    """True if ``options`` describe a stroke the GPU path can handle.

    Mirrors the constraints documented at the top of the module.
    Kept as a free function so tests can exercise the gate without
    instantiating a GL context.
    """
    if options.blend_mode != "normal":
        return False
    if options.selection is not None:
        return False
    if options.pixel_art:
        return False
    return options.kind not in ("pencil", "airbrush")


def make_brush_stroke(options, *, prefer_gpu: bool = True):
    """Return a GPU stroke when supported, else the pure-numpy CPU stroke.

    The factory checks both static compatibility (:func:`_gpu_supported`)
    and dynamic GL availability (:func:`gpu_available`); either failing
    routes back to the CPU :class:`BrushStroke` so behaviour is
    identical to the pre-GPU path. ``prefer_gpu=False`` forces the CPU
    path even when supported — the brush dispatcher uses that for
    symmetry strokes (multiple mirror strokes share one canvas, and
    each per-stroke FBO can't see the others' updates without an
    expensive per-extend re-upload). The returned object exposes the
    canonical ``begin`` / ``extend`` / ``end`` / ``stroke_damage``
    interface — callers do not need to special-case GPU vs CPU.
    """
    from Imervue.paint.brush_engine import BrushStroke
    if not prefer_gpu or not _gpu_supported(options) or not gpu_available():
        return BrushStroke(options)
    try:
        return GPUBrushStroke(options)
    except (RuntimeError, ValueError) as exc:   # pragma: no cover - GL only
        logger.warning("GPU brush stroke unavailable, falling back: %s", exc)
        return BrushStroke(options)


class GPUDabSession:
    """One stroke's worth of GPU dab rasterisation.

    Owns the per-stroke FBO, layer texture, kernel texture, and the
    saved GL state restored on :meth:`dispose`. ``stamp`` renders one
    dab into the FBO; ``read_back`` blits the FBO color buffer back
    into the supplied numpy array in-place. Constructed via
    :meth:`GPUBrushStroke.begin` so callers don't manage GL by hand.
    """

    def __init__(self, layer: np.ndarray):  # pragma: no cover - GL needs display
        if layer.ndim != 3 or layer.shape[2] != 4 or layer.dtype != np.uint8:
            raise ValueError(
                f"layer must be HxWx4 uint8 RGBA, got {layer.shape} {layer.dtype}",
            )
        self._h, self._w = layer.shape[:2]
        # Y-up ortho — necessary because GL framebuffer row 0 is the
        # bottom while ``numpy`` row 0 is the top. We upload the layer
        # bytes in numpy row order (numpy[0] becomes GL fb row 0), so
        # to make ``glReadPixels`` round-trip without an axis flip we
        # have to render dabs with the same Y-up convention. A dab at
        # canvas pixel ``(cx, cy)`` then writes to fb row ``cy`` and
        # reads back into ``layer[cy]`` — pre-fix we used a Y-down
        # ortho and the dabs landed at the mirrored row, which made
        # strokes appear to "draw circles" elsewhere on the canvas.
        self._mvp = _ortho(0.0, float(self._w), 0.0, float(self._h))
        self._program = _get_program()
        if self._program is None:
            raise RuntimeError("GPU brush shader unavailable")
        self._tex = 0
        self._kernel_tex = 0
        self._fbo = 0
        self._vbo = 0
        self._prev_fbo = 0
        self._prev_viewport = (0, 0, 0, 0)
        self._init_gl(layer)

    def _init_gl(self, layer: np.ndarray) -> None:  # pragma: no cover - GL only
        from OpenGL.GL import (
            GL_CLAMP_TO_EDGE,
            GL_COLOR_ATTACHMENT0,
            GL_FRAMEBUFFER,
            GL_FRAMEBUFFER_BINDING,
            GL_FRAMEBUFFER_COMPLETE,
            GL_LINEAR,
            GL_NEAREST,
            GL_ONE,
            GL_ONE_MINUS_SRC_ALPHA,
            GL_RGBA,
            GL_SRC_ALPHA,
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_TEXTURE_MIN_FILTER,
            GL_TEXTURE_WRAP_S,
            GL_TEXTURE_WRAP_T,
            GL_UNSIGNED_BYTE,
            GL_VIEWPORT,
            GL_BLEND,
            glBindFramebuffer,
            glBindTexture,
            glBlendFuncSeparate,
            glCheckFramebufferStatus,
            glEnable,
            glFramebufferTexture2D,
            glGenBuffers,
            glGenFramebuffers,
            glGenTextures,
            glGetIntegerv,
            glTexImage2D,
            glTexParameterf,
            glTexParameteri,
            glViewport,
        )
        self._prev_fbo = int(glGetIntegerv(GL_FRAMEBUFFER_BINDING))
        self._prev_viewport = tuple(int(v) for v in glGetIntegerv(GL_VIEWPORT))
        self._tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA, self._w, self._h, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, layer.tobytes(),
        )
        self._fbo = int(glGenFramebuffers(1))
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
        glFramebufferTexture2D(
            GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D, self._tex, 0,
        )
        if int(glCheckFramebufferStatus(GL_FRAMEBUFFER)) != int(GL_FRAMEBUFFER_COMPLETE):
            raise RuntimeError("GPU brush FBO incomplete")
        self._vbo = int(glGenBuffers(1))
        self._kernel_tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._kernel_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glBindTexture(GL_TEXTURE_2D, 0)
        glViewport(0, 0, self._w, self._h)
        glEnable(GL_BLEND)
        glBlendFuncSeparate(
            GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
            GL_ONE, GL_ONE_MINUS_SRC_ALPHA,
        )

    def _bind_session(self) -> None:  # pragma: no cover - GL only
        """Re-bind every piece of session state ``stamp`` / ``read_back``
        depend on.

        Called at the top of each public draw / read entry point because
        the canvas widget's ``paintGL`` runs between dispatcher calls
        and replaces the framebuffer binding, viewport, and blend state
        with the values it needs for the on-screen render. Without
        this re-bind, dabs would draw to the widget's default
        framebuffer (and ``glReadPixels`` would read from it) — the
        layer would never see the stroke and would in fact be
        overwritten with whatever the screen last rendered.
        """
        from OpenGL.GL import (
            GL_BLEND,
            GL_FRAMEBUFFER,
            GL_ONE,
            GL_ONE_MINUS_SRC_ALPHA,
            GL_SRC_ALPHA,
            glBindFramebuffer,
            glBlendFuncSeparate,
            glEnable,
            glViewport,
        )
        glBindFramebuffer(GL_FRAMEBUFFER, self._fbo)
        glViewport(0, 0, self._w, self._h)
        glEnable(GL_BLEND)
        glBlendFuncSeparate(
            GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
            GL_ONE, GL_ONE_MINUS_SRC_ALPHA,
        )

    def stamp(  # pragma: no cover - GL needs display server
        self,
        kernel: np.ndarray,
        color: tuple[int, int, int],
        opacity: float,
        cx: float,
        cy: float,
    ) -> None:
        """Render one dab into the FBO."""
        from OpenGL.GL import (
            GL_ARRAY_BUFFER,
            GL_DYNAMIC_DRAW,
            GL_FALSE,
            GL_FLOAT,
            GL_LUMINANCE,
            GL_RED,
            GL_TEXTURE0,
            GL_TEXTURE_2D,
            GL_TRIANGLE_FAN,
            glActiveTexture,
            glBindBuffer,
            glBindTexture,
            glBufferData,
            glDisableVertexAttribArray,
            glDrawArrays,
            glEnableVertexAttribArray,
            glTexImage2D,
            glUniform1f,
            glUniform1i,
            glUniform3f,
            glUniformMatrix4fv,
            glUseProgram,
            glVertexAttribPointer,
        )
        if kernel.ndim != 2:
            raise ValueError(f"kernel must be 2-D, got {kernel.shape}")
        kernel_f32 = np.ascontiguousarray(kernel, dtype=np.float32)
        kh, kw = kernel_f32.shape
        op = max(0.0, min(1.0, float(opacity)))
        if op <= 0.0:
            return
        self._bind_session()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self._kernel_tex)
        # GL 2.1 — no R32F universally; LUMINANCE/FLOAT carries a
        # float kernel into a single sampler channel that the shader
        # reads via ``.r``.
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_LUMINANCE, kw, kh, 0,
            GL_RED, GL_FLOAT, kernel_f32.tobytes(),
        )
        glUseProgram(self._program.program)
        glUniformMatrix4fv(self._program.u_mvp, 1, GL_FALSE, self._mvp)
        glUniform1i(self._program.u_kernel, 0)
        glUniform3f(
            self._program.u_color,
            color[0] / 255.0, color[1] / 255.0, color[2] / 255.0,
        )
        glUniform1f(self._program.u_opacity, op)
        x0 = float(cx) - kw / 2.0
        y0 = float(cy) - kh / 2.0
        verts = np.array([
            x0,           y0,           0.0, 0.0,
            x0 + kw,      y0,           1.0, 0.0,
            x0 + kw,      y0 + kh,      1.0, 1.0,
            x0,           y0 + kh,      0.0, 1.0,
        ], dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        glEnableVertexAttribArray(self._program.a_position)
        glVertexAttribPointer(
            self._program.a_position, 2, GL_FLOAT, GL_FALSE, 16,
            ctypes.c_void_p(0),
        )
        glEnableVertexAttribArray(self._program.a_texcoord)
        glVertexAttribPointer(
            self._program.a_texcoord, 2, GL_FLOAT, GL_FALSE, 16,
            ctypes.c_void_p(8),
        )
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        glDisableVertexAttribArray(self._program.a_position)
        glDisableVertexAttribArray(self._program.a_texcoord)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glUseProgram(0)

    def read_back(self, into: np.ndarray) -> None:  # pragma: no cover - GL only
        """``glReadPixels`` the FBO into ``into`` (HxWx4 uint8) in-place.

        Re-binds the session before reading so the read targets our
        FBO rather than whatever the canvas widget's ``paintGL`` left
        bound — without that the layer would silently get overwritten
        with on-screen pixels and the stroke would appear to vanish.
        """
        from OpenGL.GL import (
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            glReadPixels,
        )
        if into.shape != (self._h, self._w, 4) or into.dtype != np.uint8:
            raise ValueError(
                f"read_back target must be ({self._h}, {self._w}, 4) uint8, "
                f"got {into.shape} {into.dtype}",
            )
        if not into.flags["C_CONTIGUOUS"]:
            raise ValueError("read_back target must be C-contiguous")
        self._bind_session()
        glReadPixels(
            0, 0, self._w, self._h,
            GL_RGBA, GL_UNSIGNED_BYTE, into.ctypes.data,
        )

    def dispose(self) -> None:  # pragma: no cover - GL needs display
        """Release every GL object owned by this session."""
        from OpenGL.GL import (
            GL_FRAMEBUFFER,
            glBindFramebuffer,
            glDeleteBuffers,
            glDeleteFramebuffers,
            glDeleteTextures,
            glViewport,
        )
        glBindFramebuffer(GL_FRAMEBUFFER, self._prev_fbo)
        if self._prev_viewport != (0, 0, 0, 0):
            glViewport(*self._prev_viewport)
        if self._tex:
            glDeleteTextures(1, [self._tex])
            self._tex = 0
        if self._kernel_tex:
            glDeleteTextures(1, [self._kernel_tex])
            self._kernel_tex = 0
        if self._fbo:
            glDeleteFramebuffers(1, [self._fbo])
            self._fbo = 0
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = 0


def _get_program() -> _ShaderProgram | None:  # pragma: no cover - GL only
    """Compile / cache the dab shader for the current GL context."""
    try:
        from PySide6.QtGui import QOpenGLContext
    except ImportError:
        return None
    ctx = QOpenGLContext.currentContext()
    if ctx is None:
        return None
    key = id(ctx)
    cached = _PROGRAM_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        from OpenGL.GL import (
            GL_FRAGMENT_SHADER,
            GL_VERTEX_SHADER,
            glGetAttribLocation,
            glGetUniformLocation,
        )
        from OpenGL.GL import shaders as gl_shaders
        vs = gl_shaders.compileShader(_VERTEX_SHADER, GL_VERTEX_SHADER)
        fs = gl_shaders.compileShader(_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        program = int(gl_shaders.compileProgram(vs, fs))
    except Exception as exc:   # noqa: BLE001 - GL/driver dependent
        logger.warning("GPU brush shader compile failed: %s", exc)
        return None
    sp = _ShaderProgram(
        program=program,
        a_position=int(glGetAttribLocation(program, b"a_position")),
        a_texcoord=int(glGetAttribLocation(program, b"a_texcoord")),
        u_mvp=int(glGetUniformLocation(program, b"u_mvp")),
        u_kernel=int(glGetUniformLocation(program, b"u_kernel")),
        u_color=int(glGetUniformLocation(program, b"u_color")),
        u_opacity=int(glGetUniformLocation(program, b"u_opacity")),
    )
    _PROGRAM_CACHE[key] = sp
    return sp


class GPUBrushStroke:   # subclass ctor wired in __init__ to avoid import cycle
    """Adapter that drives :class:`GPUDabSession` through the CPU stroke API.

    Internally inherits the entire CPU :class:`BrushStroke` state
    machine — pressure / taper / kernel restyling / stabiliser
    integration — and only overrides :meth:`_paint_dab` to redirect
    each stamp onto the GPU. The layer numpy is left untouched
    during the stroke; :meth:`end` does the single ``glReadPixels``
    that syncs CPU state back so undo / save / filter all see the
    finished stroke.
    """

    def __new__(cls, options):
        # Real subclass declared at import time so the BrushStroke
        # base import doesn't create a circular dependency at module
        # load. ``GPUBrushStroke()`` always returns an instance of
        # the concrete subclass; ``cls`` is reassigned by ``_subclass``.
        subclass = _subclass()
        return subclass(options)


def _subclass():
    """Return the concrete BrushStroke subclass that paints on GPU.

    Built lazily (inside :class:`GPUBrushStroke.__new__`) so that
    importing :mod:`gpu_brush` doesn't pull in :mod:`brush_engine`
    until a stroke is actually constructed — keeps import-graph
    cycles out of the module load order.
    """
    from Imervue.paint.brush_engine import BrushStroke, DabResult, _dab_bbox

    class _GPUStroke(BrushStroke):
        def __init__(self, options):
            super().__init__(options)
            self._gpu: GPUDabSession | None = None
            self._gpu_layer: np.ndarray | None = None

        def begin(self, canvas, x, y):  # type: ignore[override]
            try:
                self._gpu = GPUDabSession(canvas)
                self._gpu_layer = canvas
            except (RuntimeError, ValueError) as exc:
                logger.warning("GPU stroke begin fell back to CPU: %s", exc)
                self._gpu = None
                self._gpu_layer = None
            result = super().begin(canvas, x, y)
            self._sync_to_layer(canvas)
            return result

        def extend(self, canvas, x, y):  # type: ignore[override]
            result = super().extend(canvas, x, y)
            self._sync_to_layer(canvas)
            return result

        def end(self, canvas, x, y):  # type: ignore[override]
            result = super().end(canvas, x, y)
            self._sync_to_layer(canvas)
            if self._gpu is not None:
                self._gpu.dispose()
                self._gpu = None
                self._gpu_layer = None
            return result

        def _sync_to_layer(self, canvas):
            """Copy the FBO's pixels back into the layer numpy buffer.

            Called after every begin / extend / end so the canvas
            widget's next ``paintGL`` rebuilds the composite from a
            current layer state — without this the user wouldn't see
            their stroke until release.
            """
            if self._gpu is None or canvas is not self._gpu_layer:
                return
            try:
                self._gpu.read_back(canvas)
            except (RuntimeError, ValueError) as exc:   # pragma: no cover - GL only
                logger.warning("GPU read_back failed, dropping session: %s", exc)
                self._gpu.dispose()
                self._gpu = None
                self._gpu_layer = None

        def _paint_dab(self, canvas, x, y, kernel, *, fade):  # type: ignore[override]
            if self._gpu is None or canvas is not self._gpu_layer:
                return super()._paint_dab(canvas, x, y, kernel, fade=fade)
            opacity = self._taper_start_opacity() * float(fade)
            if opacity <= 0.0:
                return DabResult(0, 0, 0, 0)
            bbox = _dab_bbox(canvas.shape[:2], kernel.shape, x, y)
            if bbox is None:
                return DabResult(0, 0, 0, 0)
            cx0, cy0, cx1, cy1, *_ = bbox
            self._gpu.stamp(kernel, self._options.color, opacity, x, y)
            return DabResult(cx0, cy0, cx1 - cx0, cy1 - cy0)

    return _GPUStroke


__all__ = [
    "GPUBrushStroke",
    "GPUDabSession",
    "gpu_available",
    "make_brush_stroke",
]
