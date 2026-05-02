"""Tests for the per-document undo / redo stack."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.undo_stack import UndoStack


def _doc(h: int = 4, w: int = 4) -> PaintDocument:
    document = PaintDocument()
    document.load_image(np.zeros((h, w, 4), dtype=np.uint8))
    return document


# ---------------------------------------------------------------------------
# Construction + validation
# ---------------------------------------------------------------------------


def test_initial_state_has_nothing_to_undo():
    stack = UndoStack(_doc())
    assert stack.can_undo() is False
    assert stack.can_redo() is False


def test_rejects_zero_max_levels():
    with pytest.raises(ValueError):
        UndoStack(_doc(), max_levels=0)


# ---------------------------------------------------------------------------
# Commit + undo
# ---------------------------------------------------------------------------


def test_commit_after_mutation_enables_undo():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    assert stack.can_undo() is True


def test_undo_restores_previous_state():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    document.active_layer().image[0, 0] = (0, 255, 0, 255)
    stack.commit()
    stack.undo()
    # The most recent change rolls back; first change still in place.
    assert tuple(document.active_layer().image[0, 0]) == (255, 0, 0, 255)


def test_double_undo_restores_baseline():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    document.active_layer().image[0, 0] = (0, 255, 0, 255)
    stack.commit()
    stack.undo()
    stack.undo()
    # Back to the all-zero baseline.
    assert tuple(document.active_layer().image[0, 0]) == (0, 0, 0, 0)


def test_undo_returns_false_when_stack_empty():
    document = _doc()
    stack = UndoStack(document)
    assert stack.undo() is False


# ---------------------------------------------------------------------------
# Redo
# ---------------------------------------------------------------------------


def test_redo_re_applies_undone_change():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    stack.undo()
    assert stack.can_redo() is True
    stack.redo()
    assert tuple(document.active_layer().image[0, 0]) == (255, 0, 0, 255)


def test_new_commit_drops_redo_stack():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    stack.undo()
    document.active_layer().image[0, 0] = (0, 255, 0, 255)
    stack.commit()
    # Redo stack cleared because the user kept editing.
    assert stack.can_redo() is False


def test_redo_returns_false_when_stack_empty():
    document = _doc()
    stack = UndoStack(document)
    assert stack.redo() is False


# ---------------------------------------------------------------------------
# Memory cap
# ---------------------------------------------------------------------------


def test_max_levels_caps_undo_depth():
    document = _doc()
    stack = UndoStack(document, max_levels=3)
    for v in (10, 20, 30, 40, 50):
        document.active_layer().image[0, 0, 0] = v
        stack.commit()
    # Five commits but only three undos are remembered.
    undone = 0
    while stack.undo():
        undone += 1
    assert undone == 3


# ---------------------------------------------------------------------------
# Selection round-trip
# ---------------------------------------------------------------------------


def test_undo_restores_selection_state():
    document = _doc()
    stack = UndoStack(document)
    mask = np.ones((4, 4), dtype=np.bool_)
    document.set_selection(mask)
    stack.commit()
    document.set_selection(None)
    stack.commit()
    stack.undo()
    assert document.selection() is not None
    assert bool(document.selection().all())


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


def test_clear_drops_both_stacks():
    document = _doc()
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    stack.undo()
    stack.clear()
    assert stack.can_undo() is False
    assert stack.can_redo() is False
