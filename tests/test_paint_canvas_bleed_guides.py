"""Tests for the canvas bleed-guide overlay state + integration."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.bleed_guides import preset
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _canvas(qapp):
    canvas = PaintCanvas()
    canvas.new_blank_document(width=64, height=64)
    return canvas


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------


def test_default_state_is_off_with_no_guides(qapp):
    canvas = _canvas(qapp)
    try:
        assert canvas._bleed_guides_visible is False  # noqa: SLF001
        assert canvas._bleed_guides is None  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_bleed_guides_writes_field(qapp):
    canvas = _canvas(qapp)
    try:
        guides = preset("manga_b5")
        canvas.set_bleed_guides(guides)
        assert canvas._bleed_guides is guides  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_bleed_guides_none_clears(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_bleed_guides(preset("a4"))
        canvas.set_bleed_guides(None)
        assert canvas._bleed_guides is None  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_bleed_guides_does_not_change_visibility(qapp):
    """Swapping the guides instance must not toggle the visibility
    flag — the user keeps the toggle they set."""
    canvas = _canvas(qapp)
    try:
        canvas.set_bleed_guides_visible(True)
        canvas.set_bleed_guides(preset("manga_b5"))
        assert canvas._bleed_guides_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_bleed_guides_visible_writes_field(qapp):
    canvas = _canvas(qapp)
    try:
        assert canvas._bleed_guides_visible is False  # noqa: SLF001
        canvas.set_bleed_guides_visible(True)
        assert canvas._bleed_guides_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


def test_set_bleed_guides_visible_idempotent(qapp):
    canvas = _canvas(qapp)
    try:
        canvas.set_bleed_guides_visible(True)
        canvas.set_bleed_guides_visible(True)
        assert canvas._bleed_guides_visible is True  # noqa: SLF001
    finally:
        canvas.deleteLater()


# ---------------------------------------------------------------------------
# View-menu bridge integration
# ---------------------------------------------------------------------------


def test_view_menu_toggle_propagates_to_canvas(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._view_menu_bridge   # noqa: SLF001
        bridge.toggle_bleed_guides(True)
        assert ws.canvas()._bleed_guides_visible is True  # noqa: SLF001
        bridge.toggle_bleed_guides(False)
        assert ws.canvas()._bleed_guides_visible is False  # noqa: SLF001
    finally:
        ws.deleteLater()
