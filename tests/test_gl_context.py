"""Tests for the off-paintGL texture-free GL-context guard.

The pure decision lives in ``gl_context.needs_make_current``; the re-entrant
context manager on ``GPUImageView`` wires it to the widget. Neither test
constructs a ``QOpenGLWidget`` (a light fake stands in), so no GL surface is
needed and the headless-CI crash is avoided.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.gl_context import make_current_guard, needs_make_current
from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# ---------------------------------------------------------------------------
# needs_make_current — the pure decision
# ---------------------------------------------------------------------------

def test_needs_make_current_when_context_present_not_current_and_valid():
    assert needs_make_current(True, False, True) is True


def test_needs_make_current_false_when_already_current():
    # Nested in paintGL / the close-path wrapper — a doneCurrent would wrongly
    # release the context.
    assert needs_make_current(True, True, True) is False


def test_needs_make_current_false_without_a_context():
    assert needs_make_current(False, False, True) is False


def test_needs_make_current_false_when_widget_not_valid():
    assert needs_make_current(True, False, False) is False


# ---------------------------------------------------------------------------
# _current_gl_context — the re-entrant wrapper
# ---------------------------------------------------------------------------

def _ctx_fake(ctx, *, valid):
    calls: list = []
    fake = SimpleNamespace(
        context=lambda: ctx,
        isValid=lambda: valid,
        makeCurrent=lambda: calls.append("make"),
        doneCurrent=lambda: calls.append("done"),
    )
    return fake, calls


def test_context_manager_wraps_body_when_context_not_current(qapp):
    # Real currentContext() is None here (no GL surface), so a non-None widget
    # context isn't current → makeCurrent/doneCurrent bracket the body.
    fake, calls = _ctx_fake(object(), valid=True)
    with GPUImageView._current_gl_context(fake):
        calls.append("body")
    assert calls == ["make", "body", "done"]


def test_context_manager_is_noop_without_a_context(qapp):
    fake, calls = _ctx_fake(None, valid=True)
    with GPUImageView._current_gl_context(fake):
        calls.append("body")
    assert calls == ["body"]


def test_context_manager_is_noop_when_widget_invalid(qapp):
    fake, calls = _ctx_fake(object(), valid=False)
    with GPUImageView._current_gl_context(fake):
        calls.append("body")
    assert calls == ["body"]


def test_context_manager_releases_even_when_body_raises(qapp):
    fake, calls = _ctx_fake(object(), valid=True)
    try:
        with GPUImageView._current_gl_context(fake):
            calls.append("body")
            raise ValueError("boom")
    except ValueError:
        pass
    assert calls == ["make", "body", "done"]  # doneCurrent still ran


# ---------------------------------------------------------------------------
# make_current_guard — the shared wrapper, and its widget delegations
# ---------------------------------------------------------------------------

def test_make_current_guard_wraps_when_not_current(qapp):
    fake, calls = _ctx_fake(object(), valid=True)
    with make_current_guard(fake):
        calls.append("body")
    assert calls == ["make", "body", "done"]


def test_make_current_guard_is_noop_without_a_context(qapp):
    fake, calls = _ctx_fake(None, valid=True)
    with make_current_guard(fake):
        calls.append("body")
    assert calls == ["body"]


def test_puppet_canvas_delegates_to_the_shared_guard(qapp):
    from Imervue.puppet.canvas import PuppetCanvas
    fake, calls = _ctx_fake(object(), valid=True)
    with PuppetCanvas._current_gl_context(fake):
        calls.append("body")
    assert calls == ["make", "body", "done"]


def test_paint_canvas_delegates_to_the_shared_guard(qapp):
    from Imervue.paint.canvas import PaintCanvas
    fake, calls = _ctx_fake(object(), valid=True)
    with PaintCanvas._current_gl_context(fake):
        calls.append("body")
    assert calls == ["make", "body", "done"]
