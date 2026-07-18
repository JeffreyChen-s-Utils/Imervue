"""GPU brush strokes must not leak their framebuffer/textures.

Two abandon paths dropped a live GPU session without freeing it:
  * _init_gl raising (e.g. an incomplete FBO) after it had already allocated
    the texture + framebuffer -- the caller never gets an instance to dispose.
  * a tool switch mid-stroke routes through BrushTool.cancel(), which cleared
    _strokes without ending them, so the GPU session never reached end().
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import gpu_brush
from Imervue.paint.tools.painting import BrushTool


def test_init_gl_failure_disposes_partial_allocation(monkeypatch):
    from OpenGL import GL

    freed = {"tex": [], "fbo": [], "buf": []}
    monkeypatch.setattr(GL, "glDeleteTextures", lambda n, ids: freed["tex"].extend(ids))
    monkeypatch.setattr(GL, "glDeleteFramebuffers", lambda n, ids: freed["fbo"].extend(ids))
    monkeypatch.setattr(GL, "glDeleteBuffers", lambda n, ids: freed["buf"].extend(ids))
    monkeypatch.setattr(GL, "glBindFramebuffer", lambda *a: None)
    monkeypatch.setattr(GL, "glViewport", lambda *a: None)
    monkeypatch.setattr(gpu_brush, "_get_program", lambda: object())

    def fake_init_gl(self, layer):
        # Simulate reaching the FBO-incomplete raise after allocating tex + fbo.
        self._tex = 7
        self._fbo = 9
        raise RuntimeError("GPU brush FBO incomplete")

    monkeypatch.setattr(gpu_brush.GPUDabSession, "_init_gl", fake_init_gl)

    layer = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(RuntimeError, match="incomplete"):
        gpu_brush.GPUDabSession(layer)

    assert freed["tex"] == [7]   # the partially-allocated texture was freed
    assert freed["fbo"] == [9]   # ...and the framebuffer, not leaked


def test_gpu_stroke_dispose_frees_session_idempotently():
    gpu_stroke_cls = gpu_brush._subclass()
    freed: list[int] = []
    fake = SimpleNamespace(
        _gpu=SimpleNamespace(dispose=lambda: freed.append(1)),
        _gpu_layer=object(),
    )

    gpu_stroke_cls.dispose(fake)
    assert freed == [1]
    assert fake._gpu is None
    assert fake._gpu_layer is None

    gpu_stroke_cls.dispose(fake)   # idempotent: no double free, no crash
    assert freed == [1]


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self):
        for callback in self._callbacks:
            callback()


def test_program_cache_evicts_entry_when_context_destroyed():
    # id(ctx) is reused after a QOpenGLContext is freed; a stale cache entry
    # would hand a new context the dead one's invalid program. The entry must be
    # dropped the moment the context signals destruction.
    signal = _FakeSignal()
    ctx = SimpleNamespace(aboutToBeDestroyed=signal)
    sentinel = object()
    gpu_brush._PROGRAM_CACHE.pop(4242, None)

    gpu_brush._cache_program(ctx, 4242, sentinel)
    assert gpu_brush._PROGRAM_CACHE[4242] is sentinel

    signal.emit()   # context destroyed
    assert 4242 not in gpu_brush._PROGRAM_CACHE


def test_program_cache_tolerates_context_without_signal():
    # A context object that can't be wired must not break caching.
    ctx = SimpleNamespace()   # no aboutToBeDestroyed
    sentinel = object()
    gpu_brush._PROGRAM_CACHE.pop(4243, None)

    gpu_brush._cache_program(ctx, 4243, sentinel)
    assert gpu_brush._PROGRAM_CACHE[4243] is sentinel
    gpu_brush._PROGRAM_CACHE.pop(4243, None)


def test_brush_tool_cancel_disposes_every_active_stroke():
    disposed: list[str] = []
    s1 = SimpleNamespace(dispose=lambda: disposed.append("s1"))
    s2 = SimpleNamespace(dispose=lambda: disposed.append("s2"))
    fake = SimpleNamespace(
        _strokes=[s1, s2], _stabilizer=object(), _stroke_anchor=(1, 2),
    )

    BrushTool.cancel(fake)

    assert disposed == ["s1", "s2"]   # both GPU sessions released
    assert fake._strokes == []
    assert fake._stabilizer is None
    assert fake._stroke_anchor is None
