"""Tests for the canvas drag-drop highlight overlay."""
from __future__ import annotations

import pytest

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture
def canvas(qapp):
    from Imervue.paint.canvas import PaintCanvas
    c = PaintCanvas()
    yield c
    c.deleteLater()


def test_drag_overlay_default_false(canvas):
    """A fresh canvas paints without the drag highlight — the
    overlay should only appear during an active drag-over."""
    assert canvas._drag_overlay_active is False  # noqa: SLF001


def test_set_drag_overlay_active_true_flips_flag(canvas):
    canvas.set_drag_overlay_active(True)
    assert canvas._drag_overlay_active is True  # noqa: SLF001


def test_set_drag_overlay_active_false_clears_flag(canvas):
    canvas.set_drag_overlay_active(True)
    canvas.set_drag_overlay_active(False)
    assert canvas._drag_overlay_active is False  # noqa: SLF001


def test_set_drag_overlay_active_idempotent(canvas):
    """Calling with the same value twice doesn't churn — important
    because Qt fires dragMove on every cursor sample, which would
    otherwise trigger redundant repaint requests."""
    canvas.set_drag_overlay_active(True)
    # Force update tracking via a flag the test installs.
    update_calls = []
    canvas.update = lambda: update_calls.append(1)  # type: ignore[method-assign]
    canvas.set_drag_overlay_active(True)
    assert update_calls == []


def test_set_drag_overlay_coerces_truthy_input(canvas):
    """Truthy non-bool inputs (e.g. ``1`` from a Qt enum) still set
    a real bool so subsequent identity comparisons in paintGL stay
    sensible."""
    canvas.set_drag_overlay_active(1)
    assert canvas._drag_overlay_active is True  # noqa: SLF001
    canvas.set_drag_overlay_active(0)
    assert canvas._drag_overlay_active is False  # noqa: SLF001
