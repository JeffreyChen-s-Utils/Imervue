"""Paint workspace: first-stroke undo (GP6) and dropped-file dock rebind (GP7).

Both are driven on the workspace methods unbound with fakes + a real
PaintDocument -- no QOpenGLWidget is constructed, so this runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from PIL import Image

from Imervue.paint.document import PaintDocument
from Imervue.paint.paint_workspace import PaintWorkspace


class _FakeCanvas:   # a real class is hashable (SimpleNamespace is not)
    def __init__(self, doc):
        self._doc = doc

    def document(self):
        return self._doc


def test_undo_stack_seeded_at_bind_makes_first_stroke_undoable():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    canvas = _FakeCanvas(doc)
    ws = SimpleNamespace(_canvas=canvas, _undo_stacks={})

    # Seed at bind time (blank state) as _ensure_undo_stack does, BEFORE any
    # stroke. Lazily creating the stack on the first commit captured the
    # post-stroke state as the baseline and lost the first undo.
    stack = PaintWorkspace._undo_stack.fget(ws)
    doc.active_layer().image[0, 0] = (255, 0, 0, 255)   # the first stroke
    stack.commit()
    assert stack.undo() is True
    assert tuple(doc.active_layer().image[0, 0]) == (0, 0, 0, 0)   # blank restored


def test_dropped_raster_routes_through_the_load_image_wrapper(tmp_path):
    path = tmp_path / "x.png"
    Image.fromarray(np.zeros((4, 4, 4), dtype=np.uint8), "RGBA").save(str(path))
    loaded: list = []
    ws = SimpleNamespace(
        load_image=lambda arr: loaded.append(arr),   # the wrapper (rebinds dock)
        _file_menu_bridge=None,
    )
    PaintWorkspace._open_dropped_path(ws, str(path))
    # Went through self.load_image, not self._canvas.load_image (which would have
    # left the layer dock bound to the replaced document).
    assert len(loaded) == 1
    assert loaded[0].shape == (4, 4, 4)


# ---------------------------------------------------------------------------
# Ctrl+Z mid-stroke guard — undo/redo defer while a mouse button is held
# ---------------------------------------------------------------------------


def test_pointer_button_held_detects_left_button():
    from PySide6.QtCore import Qt

    from Imervue.paint.paint_workspace import _pointer_button_held
    assert _pointer_button_held(Qt.MouseButton.LeftButton) is True
    assert _pointer_button_held(Qt.MouseButton.NoButton) is False
    assert _pointer_button_held(Qt.MouseButton.RightButton) is False
    assert _pointer_button_held(
        Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton) is True


def test_undo_deferred_while_pointer_button_held():
    undo_calls: list = []
    ws = SimpleNamespace(
        _pointer_stroke_active=lambda: True,
        _undo_stack=SimpleNamespace(undo=lambda: undo_calls.append(True) or True),
        _canvas=SimpleNamespace(invalidate_texture=lambda: None, update=lambda: None),
        _notify_history_action=lambda k: None,
        _notify_history_empty=lambda k: None,
    )
    PaintWorkspace.undo(ws)
    assert undo_calls == []   # the undo stack is never touched mid-stroke


def test_undo_proceeds_when_no_button_held():
    undo_calls: list = []
    actions: list = []
    ws = SimpleNamespace(
        _pointer_stroke_active=lambda: False,
        _undo_stack=SimpleNamespace(undo=lambda: undo_calls.append(True) or True),
        _canvas=SimpleNamespace(invalidate_texture=lambda: None, update=lambda: None),
        _notify_history_action=lambda k: actions.append(k),
        _notify_history_empty=lambda k: None,
    )
    PaintWorkspace.undo(ws)
    assert undo_calls == [True]
    assert actions == ["undo"]
