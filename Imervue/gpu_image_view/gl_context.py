"""Deciding when a GL texture free issued outside ``paintGL`` needs the context.

Deep-zoom texture frees (``TileManager.clear``, the minimap texture, the
memory-pressure trim) run from signal / key / menu handlers — never inside
``paintGL`` — so the widget's GL context isn't current and ``glDeleteTextures``
is silently dropped, leaking VRAM on every image switch. The widget makes its
context current around those frees; this pure predicate holds the "should I?"
decision so it is testable without a live GL surface.
"""
from __future__ import annotations

import contextlib


def needs_make_current(has_context: bool, is_current: bool,
                       is_valid: bool) -> bool:
    """Whether to ``makeCurrent`` before issuing ``glDeleteTextures``.

    Make the context current unless there is none, it is already current
    (nested inside ``paintGL`` or the close-path wrapper — where a following
    ``doneCurrent`` would wrongly release it), or the widget isn't valid yet.
    """
    return has_context and not is_current and is_valid


@contextlib.contextmanager
def make_current_guard(widget):
    """Make *widget*'s GL context current for GL frees issued outside paintGL.

    Shared by every QOpenGLWidget that frees textures/buffers from signal, key,
    menu, timer or close handlers (the deep-zoom viewer, the puppet canvas, the
    paint canvas): without a current context ``glDelete*`` is silently dropped
    and the resource leaks. Re-entrant — a no-op when the context is already
    current (nested in a paint or a close-path wrapper, where a stray
    ``doneCurrent`` would wrongly release it) or the widget has no valid context.
    """
    from PySide6.QtGui import QOpenGLContext
    ctx = widget.context()
    made = False
    if needs_make_current(
        ctx is not None,
        ctx is not None and QOpenGLContext.currentContext() is ctx,
        widget.isValid(),
    ):
        with contextlib.suppress(Exception):
            widget.makeCurrent()
            made = True
    try:
        yield
    finally:
        if made:
            with contextlib.suppress(Exception):
                widget.doneCurrent()
