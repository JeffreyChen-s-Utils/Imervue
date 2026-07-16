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
