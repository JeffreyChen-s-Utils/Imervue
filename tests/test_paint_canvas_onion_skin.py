"""Tests for the canvas onion-skin overlay state + source plumbing."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _canvas(qapp):
    canvas = PaintCanvas()
    canvas.new_blank_document(width=32, height=32)
    return canvas


# ---------------------------------------------------------------------------
# set_onion_skin_visible
# ---------------------------------------------------------------------------


def test_set_onion_skin_visible_writes_field(qapp):
    canvas = _canvas(qapp)
    try:
        assert canvas._onion_skin_visible is False  # noqa: SLF001
        canvas.set_onion_skin_visible(True)
        assert canvas._onion_skin_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_onion_skin_visible_idempotent(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_onion_skin_visible(True)
        canvas.set_onion_skin_visible(True)
        assert canvas._onion_skin_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# set_onion_skin_source
# ---------------------------------------------------------------------------


def test_set_onion_skin_source_stashes_callable(qapp):
    canvas = _canvas(qapp)
    try:
        def _src():
            return None
        canvas.set_onion_skin_source(_src)
        assert canvas._onion_skin_source is _src   # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_onion_skin_source_invalidates_texture(qapp):
    """Swapping the source must drop the cached texture so the next
    paint re-uploads from the new buffer rather than blitting the
    stale animation frame."""
    canvas = _canvas(qapp)
    try:
        # Pretend a prior session uploaded a texture.
        canvas._onion_skin_texture = 42  # noqa: SLF001
        canvas._onion_skin_buffer_id = 99  # noqa: SLF001
        canvas.set_onion_skin_source(lambda: None)
        assert canvas._onion_skin_texture is None  # noqa: SLF001
        assert canvas._onion_skin_buffer_id is None  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_onion_skin_source_accepts_none(qapp):
    """Passing ``None`` clears the source — the canvas just stops
    rendering the overlay rather than crashing on the next paint."""
    canvas = _canvas(qapp)
    try:
        canvas.set_onion_skin_source(None)
        assert canvas._onion_skin_source is None  # noqa: SLF001
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------------


def test_source_returning_none_does_not_upload(qapp):
    """Source returns None ⇒ overlay is skipped this frame; the
    canvas's texture handle stays unset."""
    canvas = _canvas(qapp)
    try:
        canvas.set_onion_skin_visible(True)
        canvas.set_onion_skin_source(lambda: None)
        # The texture upload only fires inside paintGL which we
        # can't drive headlessly. Verify the wiring at least keeps
        # the texture handle reset.
        assert canvas._onion_skin_texture is None  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_source_returning_buffer_persists(qapp):
    canvas = _canvas(qapp)
    try:
        buffer = np.zeros((32, 32, 4), dtype=np.uint8)
        canvas.set_onion_skin_source(lambda: buffer)
        # Sanity — the source returns a real array.
        assert canvas._onion_skin_source() is buffer  # noqa: SLF001
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# View-menu bridge integration
# ---------------------------------------------------------------------------


def test_view_menu_toggle_propagates_to_canvas(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_onion_skin(True)
        assert ws.canvas()._onion_skin_visible is True  # noqa: SLF001
        bridge.toggle_onion_skin(False)
        assert ws.canvas()._onion_skin_visible is False  # noqa: SLF001
    finally:
        ws.deleteLater()
