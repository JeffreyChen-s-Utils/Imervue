"""Pins the state a freshly constructed ``PaintCanvas`` starts from.

Every attribute the constructor seeds, its widget flags, the document
subscription and the marquee timer, so splitting ``__init__`` into section
initialisers cannot drop, retype or reorder any of it.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt, QTimer

from _qt_skip import pytestmark  # noqa: E402,F401
from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.document import PaintDocument

_DEFAULTS = {
    "_texture": None, "_checker_texture": None, "_drag_overlay_active": False,
    "_needs_upload": False, "_grid_vbo": None, "_grid_vbo_size": None,
    "_grid_vbo_vertices": 0, "_zoom": 1.0, "_pan_x": 0.0, "_pan_y": 0.0,
    "_rotation_deg": 0.0, "_pixel_grid_visible": False, "_size_hud": None,
    "_tool_state_for_hud": None, "_onion_skin_visible": False,
    "_onion_skin_source": None, "_onion_skin_texture": None,
    "_onion_skin_buffer_id": None, "_bleed_guides_visible": False,
    "_bleed_guides": None, "_fit_pending": False, "_fitted_widget_size": (0, 0),
    "_last_resize_size": (0, 0), "_user_view_locked": False, "_dispatcher": None,
    "_panning": False, "_pan_anchor": (0, 0),
    "_marquee_segments": None, "_marquee_phase": 0, "_tool_overlay": None,
}


@pytest.fixture
def canvas(qapp):
    widget = PaintCanvas()
    yield widget
    widget.deleteLater()


def test_seeded_attributes(canvas):
    actual = {name: getattr(canvas, name) for name in _DEFAULTS}
    assert actual == _DEFAULTS
    assert type(canvas._zoom) is float  # noqa: SLF001
    assert canvas._pending_damage == EMPTY_DAMAGE  # noqa: SLF001


def test_widget_flags(canvas):
    assert canvas.hasMouseTracking()
    assert canvas.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert canvas.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    assert canvas.acceptDrops()


def test_document_is_subscribed(canvas):
    assert isinstance(canvas._document, PaintDocument)  # noqa: SLF001
    assert callable(canvas._document_unsubscribe)  # noqa: SLF001
    canvas._needs_upload = False  # noqa: SLF001
    canvas._document.load_image(np.zeros((4, 4, 4), dtype=np.uint8))  # noqa: SLF001
    assert canvas._needs_upload  # noqa: SLF001


def test_marquee_timer(canvas):
    timer = canvas._marquee_timer  # noqa: SLF001
    assert isinstance(timer, QTimer)
    assert timer.parent() is canvas
    assert timer.interval() == 120
    assert not timer.isActive()
    phase = canvas._marquee_phase  # noqa: SLF001
    timer.timeout.emit()
    assert canvas._marquee_phase != phase  # noqa: SLF001
