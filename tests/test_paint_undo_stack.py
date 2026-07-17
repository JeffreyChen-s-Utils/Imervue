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


# ---------------------------------------------------------------------------
# A whole-canvas transform changes layer dimensions; undo must not crash on a
# stale (old-size) snapshot.
# ---------------------------------------------------------------------------


def test_undo_survives_a_dimension_change_after_snapshot():
    document = _doc(4, 6)   # non-square so a 90° rotate changes the shape
    stack = UndoStack(document)
    document.active_layer().image[0, 0] = (255, 0, 0, 255)
    stack.commit()                        # snapshot captured at 4x6
    assert document.rotate_90_cw() is True  # layers become 6x4
    # The 4x6 snapshot no longer matches the 6x4 layers -- np.copyto would raise
    # a broadcast ValueError. _restore must skip the mismatched layer instead.
    assert stack.undo() is True           # must not raise


def test_reset_undo_stack_clears_and_is_guarded():
    from types import SimpleNamespace

    from Imervue.paint.image_menu import _reset_undo_stack

    cleared: list = []
    ws = SimpleNamespace(
        _undo_stack=SimpleNamespace(clear=lambda: cleared.append(True)))
    _reset_undo_stack(ws)
    assert cleared == [True]
    # A workspace with no undo stack (or mid-teardown) is a safe no-op.
    _reset_undo_stack(SimpleNamespace())


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
# Structural layer changes between commits — snapshots map by identity
# ---------------------------------------------------------------------------


def test_undo_after_layer_add_restores_by_identity_not_index():
    """Regression: with index-based restore, adding a layer between
    commits made undo write another layer's captured pixels into the
    newcomer. Snapshots now map pixels by layer identity."""
    document = _doc()
    layer_a = document.add_layer(name="A")
    layer_b = document.add_layer(name="B")        # stack: [BG, A, B]
    stack = UndoStack(document)
    layer_a.image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    document.set_active_layer(1)                  # insert the new layer mid-stack
    new_layer = document.add_layer(name="New")    # stack: [BG, A, New, B]
    new_layer.image[1, 1] = (9, 9, 9, 255)
    stack.commit()
    stack.undo()
    # A keeps its stroke (it predates the restored snapshot)...
    assert tuple(layer_a.image[0, 0]) == (255, 0, 0, 255)
    # ...B stays empty, and the newcomer must NOT receive B's captured
    # pixels — the snapshot simply has nothing for it.
    assert tuple(layer_b.image[1, 1]) == (0, 0, 0, 0)
    assert tuple(new_layer.image[1, 1]) == (9, 9, 9, 255)


def test_undo_after_layer_move_restores_moved_layer_pixels():
    """Reordering layers between commits must not swap their undo
    contents — the captured image follows the layer object."""
    document = _doc()
    layer_a = document.add_layer(name="A")        # stack: [BG, A], active=A
    stack = UndoStack(document)
    layer_a.image[0, 0] = (255, 0, 0, 255)
    stack.commit()
    layer_a.image[0, 0] = (0, 255, 0, 255)
    stack.commit()
    document.move_active_layer(up=False)          # stack: [A, BG]
    stack.undo()
    assert tuple(layer_a.image[0, 0]) == (255, 0, 0, 255)
    assert tuple(document.layer_at(1).image[0, 0]) == (0, 0, 0, 0)


def test_undo_after_layer_delete_skips_the_dead_layer():
    """Deleting a layer between commits must not shift its captured
    pixels into the next layer down the old index order."""
    document = _doc()
    layer_a = document.add_layer(name="A")
    layer_b = document.add_layer(name="B")        # stack: [BG, A, B]
    stack = UndoStack(document)
    layer_a.image[0, 0] = (255, 0, 0, 255)
    layer_b.image[0, 0] = (0, 0, 255, 255)
    stack.commit()
    layer_b.image[0, 0] = (7, 7, 7, 255)
    stack.commit()
    document.set_active_layer(1)
    document.remove_active_layer()                # stack: [BG, B]
    del layer_a
    stack.undo()                                  # must not raise
    assert tuple(layer_b.image[0, 0]) == (0, 0, 255, 255)
    assert tuple(document.layer_at(0).image[0, 0]) == (0, 0, 0, 0)


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
