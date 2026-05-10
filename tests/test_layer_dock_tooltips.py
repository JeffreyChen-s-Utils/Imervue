"""Tests for the LayerDock button tooltips — phase 34i.

Each row of layer-action buttons (add / remove / move up / move down
/ duplicate) used to render its glyph with no tooltip, so the artist
had to memorise what ``⧉`` meant. We now produce a tooltip that
combines the documented label with the shortcut from the registry,
e.g. ``Add layer (Ctrl+Shift+N)``.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QToolButton

from Imervue.paint.dock_panels import LayerDock
from Imervue.paint.document import PaintDocument


@pytest.fixture
def layer_dock(qapp):
    import numpy as np
    doc = PaintDocument()
    doc.load_image(np.zeros((48, 48, 4), dtype=np.uint8))
    dock = LayerDock(doc)
    yield dock
    dock.deleteLater()


def _row_buttons(dock: LayerDock) -> list[QToolButton]:
    """Return the action-button row in left-to-right order."""
    return [
        b for b in dock.findChildren(QToolButton)
        if b.text() in ("+", "−", "↑", "↓", "⧉")
    ]


def test_layer_buttons_have_tooltips(layer_dock):
    buttons = _row_buttons(layer_dock)
    assert len(buttons) == 5
    for btn in buttons:
        assert btn.toolTip(), f"button {btn.text()!r} missing tooltip"


def test_add_layer_tooltip_includes_shortcut(layer_dock):
    add_btn = next(b for b in _row_buttons(layer_dock) if b.text() == "+")
    # The bracket-wrapped suffix means the hotkey was successfully
    # appended; the underlying registry default is Ctrl+Shift+N.
    assert "Ctrl+Shift+N" in add_btn.toolTip()


def test_duplicate_tooltip_includes_shortcut(layer_dock):
    dup_btn = next(b for b in _row_buttons(layer_dock) if b.text() == "⧉")
    assert "Ctrl+J" in dup_btn.toolTip()


def test_move_up_tooltip_includes_shortcut(layer_dock):
    up_btn = next(b for b in _row_buttons(layer_dock) if b.text() == "↑")
    assert "Ctrl+]" in up_btn.toolTip()


def test_move_down_tooltip_includes_shortcut(layer_dock):
    down_btn = next(b for b in _row_buttons(layer_dock) if b.text() == "↓")
    assert "Ctrl+[" in down_btn.toolTip()


def test_remove_tooltip_has_no_shortcut_suffix(layer_dock):
    """The Delete-layer action has no entry in the shortcut registry,
    so the tooltip should be the bare label rather than the same label
    with an empty bracket pair."""
    minus = next(b for b in _row_buttons(layer_dock) if b.text() == "−")
    assert "(" not in minus.toolTip()


# ---------------------------------------------------------------------------
# PageNavigatorDock action buttons — phase 34i continuation
# ---------------------------------------------------------------------------


def test_page_navigator_action_buttons_have_tooltips(qapp):
    from Imervue.paint.dock_panels import PageNavigatorDock
    dock = PageNavigatorDock()
    try:
        glyph_buttons = [
            b for b in dock.findChildren(QToolButton)
            if b.text() in ("+", "−", "↑", "↓")
        ]
        assert len(glyph_buttons) == 4
        for btn in glyph_buttons:
            assert btn.toolTip(), f"page button {btn.text()!r} missing tooltip"
    finally:
        dock.deleteLater()
