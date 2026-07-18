"""Unit tests for ``canvas._preserved_gl_render_state``.

The context manager is pure GL-state bookkeeping, so it is exercised by
monkeypatching the module-level GL symbols — no ``QOpenGLWidget`` is
constructed, which means these run on headless CI (unlike the widget smoke
tests that need the ``_qt_skip`` marker).
"""
from __future__ import annotations

import pytest

from Imervue.puppet import canvas


def _patch_gl(monkeypatch, *, clear, viewport, sink):
    """Stub the GL symbols the context manager touches, recording every call
    into ``sink`` as ``(name, args)`` tuples."""
    monkeypatch.setattr(canvas, "glGetFloatv", lambda _enum: clear)
    monkeypatch.setattr(canvas, "glGetIntegerv", lambda _enum: viewport)
    monkeypatch.setattr(canvas, "glClearColor", lambda *a: sink.append(("clear", a)))
    monkeypatch.setattr(canvas, "glViewport", lambda *a: sink.append(("viewport", a)))
    monkeypatch.setattr(canvas, "glMatrixMode", lambda m: sink.append(("mode", m)))
    monkeypatch.setattr(canvas, "glPushMatrix", lambda: sink.append(("push", ())))
    monkeypatch.setattr(canvas, "glPopMatrix", lambda: sink.append(("pop", ())))


def test_restores_clear_colour_and_viewport(monkeypatch):
    saved_clear = (0.13, 0.13, 0.15, 1.0)
    saved_viewport = (0, 0, 800, 600)
    calls: list[tuple[str, tuple]] = []
    _patch_gl(monkeypatch, clear=saved_clear, viewport=saved_viewport, sink=calls)

    with canvas._preserved_gl_render_state():
        # Body corrupts the state exactly like an off-screen FBO render does.
        canvas.glClearColor(1.0, 0.0, 1.0, 1.0)   # chroma-key magenta
        canvas.glViewport(0, 0, 640, 480)         # FBO size

    clears = [args for tag, args in calls if tag == "clear"]
    viewports = [args for tag, args in calls if tag == "viewport"]
    # The LAST clear/viewport calls must put back the saved values, not leave
    # the magenta / FBO-size the body set (the desktop-pet corruption bug).
    assert clears[-1] == pytest.approx(saved_clear)
    assert viewports[-1] == saved_viewport


def test_balances_matrix_stack_and_restores_on_early_exit(monkeypatch):
    """A zero-sized document returns early from inside the ``with`` block; the
    matrices must still be popped (else GL_STACK_OVERFLOW after ~32 frames) and
    the clear colour / viewport still restored."""
    calls: list[tuple[str, tuple]] = []
    _patch_gl(monkeypatch, clear=(0.0, 0.0, 0.0, 0.0), viewport=(0, 0, 1, 1), sink=calls)

    with pytest.raises(RuntimeError), canvas._preserved_gl_render_state():
        raise RuntimeError("mimic early exit")

    pushes = [c for c in calls if c[0] == "push"]
    pops = [c for c in calls if c[0] == "pop"]
    assert len(pushes) == len(pops) == 2   # projection + modelview, balanced
    # Restore still happened despite the exception.
    assert any(tag == "clear" for tag, _ in calls)
    assert any(tag == "viewport" for tag, _ in calls)


def test_matrices_pushed_before_body_and_popped_after(monkeypatch):
    calls: list[tuple[str, tuple]] = []
    _patch_gl(monkeypatch, clear=(0.0, 0.0, 0.0, 0.0), viewport=(0, 0, 1, 1), sink=calls)

    marker = ("body", ())
    with canvas._preserved_gl_render_state():
        calls.append(marker)

    tags = [c[0] for c in calls]
    body_at = tags.index("body")
    # Two pushes precede the body; two pops follow it.
    assert tags[:body_at].count("push") == 2
    assert tags[body_at + 1:].count("pop") == 2
