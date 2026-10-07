"""Byte budgets include baseline, Undo and Redo without weakening restoration."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument
from Imervue.paint.tool_dispatcher import DispatcherHooks, ToolDispatcher
from Imervue.paint.tool_state import ToolState
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.undo_stack import MAX_UNDO_BYTES, UndoStack


def _doc(size=512):
    doc = PaintDocument()
    doc.load_image(np.zeros((size, size, 4), dtype=np.uint8))
    return doc


@pytest.mark.parametrize("budget", [0, -1])
def test_invalid_budget(budget):
    with pytest.raises(ValueError, match="max_bytes"):
        UndoStack(_doc(2), max_bytes=budget)


def test_single_state_over_budget_keeps_live_content_but_no_history(caplog):
    doc = _doc(10)
    stack = UndoStack(doc, max_bytes=1)
    assert stack.history_bytes == 0
    assert not stack.can_undo()
    doc.active_layer().image[:] = 255
    stack.commit()
    assert stack.history_bytes == 0
    assert not stack.undo()
    assert "exceeds history budget" in caplog.text
    np.testing.assert_array_equal(doc.active_layer().image, 255)


def test_byte_limit_prunes_oldest_undo_and_counts_redo():
    doc = _doc()
    # Four identical tiles initially share one payload. Fully distinct edits
    # add one payload each, unlike the ordinary regional brush path.
    budget = UndoStack(doc).history_bytes + 2 * 256 * 256 * 4 + 40_000
    stack = UndoStack(doc, max_bytes=budget)
    for value in range(1, 8):
        doc.active_layer().image[:] = value
        stack.commit()
        assert stack.history_bytes <= budget
    assert len(stack._undo) == 2
    assert stack.undo()
    np.testing.assert_array_equal(doc.active_layer().image, 6)
    assert stack.history_bytes <= budget
    assert stack.redo()
    np.testing.assert_array_equal(doc.active_layer().image, 7)
    assert stack.history_bytes <= budget


def test_small_strokes_store_deltas_and_keep_complete_metadata():
    doc = _doc()
    doc.add_layer(name="ink")
    stack = UndoStack(doc)
    initial = stack.history_bytes
    array = doc.active_layer().image
    for value in range(1, 5):
        array[10:42, 10:42] = value
        doc.active_layer().opacity = value / 10
        stack.commit(regions=((array, DamageRect(10, 10, 32, 32)),))
    assert stack.history_bytes < initial + 4 * (256 * 256 * 4 + 12_000)
    assert stack.history_bytes < MAX_UNDO_BYTES
    for value in range(3, -1, -1):
        assert stack.undo()
        np.testing.assert_array_equal(doc.active_layer().image[10:42, 10:42], value)
        assert doc.active_layer().opacity == (value / 10 if value else 1)
    for value in range(1, 5):
        assert stack.redo()
        np.testing.assert_array_equal(doc.active_layer().image[10:42, 10:42], value)


def test_six_non_repeating_layers_meet_storage_target_without_interning_advantage():
    doc = _doc(1024)
    rng = np.random.default_rng(64)
    doc.active_layer().image[:] = rng.integers(0, 256, (1024, 1024, 4), dtype=np.uint8)
    for _ in range(5):
        doc.add_layer().image[:] = rng.integers(0, 256, (1024, 1024, 4), dtype=np.uint8)
    stack = UndoStack(doc)
    array = doc.active_layer().image
    for _ in range(3):
        array[10:42, 10:42, 0] ^= 1
        stack.commit(regions=((array, DamageRect(10, 10, 32, 32)),))
    four_full_snapshots = sum(layer.image.nbytes for layer in doc.layers()) * 4
    assert stack.history_bytes <= four_full_snapshots * .4


def test_uninstrumented_edits_masks_selection_and_abandoned_redo_are_owned():
    doc = _doc(8)
    doc.add_layer_mask(fill=200)
    doc.set_selection(np.ones(doc.shape, dtype=np.bool_))
    stack = UndoStack(doc)
    doc.active_layer().image[0, 0] = 255
    doc.active_layer().mask[0, 0] = 100
    doc.selection()[0, 0] = False
    stack.commit()
    saved = stack.committed_snapshot()
    assert stack.undo()
    assert doc.active_layer().mask[0, 0] == 200
    assert doc.selection()[0, 0]
    doc.active_layer().image[1, 1] = 80
    stack.commit()
    assert not stack.can_redo()
    independent = saved.materialize()
    assert independent.active_layer().mask[0, 0] == 100
    assert not independent.selection()[0, 0]
    independent.active_layer().image[:] = 0
    assert saved.materialize().active_layer().image[0, 0, 0] == 255
    stack.clear()
    assert not stack.can_undo()
    assert not stack.can_redo()


@pytest.mark.parametrize("tool", ["brush", "eraser"])
def test_real_dispatcher_reports_entire_gesture_only_during_commit(tool):
    doc = _doc()
    doc.active_layer().image[:] = 255
    stack = UndoStack(doc)
    before = doc.active_layer().image.copy()
    state = ToolState()
    state.set_tool(tool)
    state.set_brush(size=7, opacity=1, hardness=1)
    hints = []

    def commit():
        hints.append(dispatcher.history_regions)
        stack.commit(regions=dispatcher.history_regions)

    dispatcher = ToolDispatcher(state, lambda: doc.active_layer().image,
                                DispatcherHooks(commit_undo=commit))
    for phase, x, y in [("press", 10, 10), ("move", 270, 270), ("release", 400, 400)]:
        dispatcher(PointerEvent(phase=phase, x=x, y=y, button=1,
                                modifiers=0, pressure=1))
    assert len(hints) == 1
    assert hints[0] is not None
    assert hints[0][0][1].x2 >= 400
    assert dispatcher.history_regions is None
    after = doc.active_layer().image.copy()
    assert stack.undo()
    np.testing.assert_array_equal(doc.active_layer().image, before)
    assert stack.redo()
    np.testing.assert_array_equal(doc.active_layer().image, after)
    dispatcher.commit_external_edit()
    assert hints[-1] is None


def test_dispatcher_missing_damage_and_tool_switch_fall_back_to_full_capture():
    doc = _doc(16)
    state = ToolState()
    state.set_tool("brush")
    observed = []
    dispatcher = ToolDispatcher(state, lambda: doc.active_layer().image,
                                DispatcherHooks(commit_undo=lambda: observed.append(
                                    dispatcher.history_regions)))

    class Handler:
        def handle(self, evt, array):
            array[0, 0] = 255
            return True

    dispatcher._handlers["brush"] = Handler()
    dispatcher(PointerEvent(phase="press", x=0, y=0, button=1, modifiers=0, pressure=1))
    state.set_tool("hand")
    dispatcher(PointerEvent(phase="release", x=0, y=0, button=0, modifiers=0, pressure=1))
    assert observed == [None]


def test_partial_tool_error_commits_with_full_capture_and_releases_hint():
    doc = _doc()
    stack = UndoStack(doc)
    state = ToolState()
    state.set_tool("brush")
    hints = []

    def commit():
        hints.append(dispatcher.history_regions)
        stack.commit(regions=dispatcher.history_regions)

    dispatcher = ToolDispatcher(state, lambda: doc.active_layer().image,
                                DispatcherHooks(commit_undo=commit))

    class Handler:
        last_damage = DamageRect(0, 0, 1, 1)

        def handle(self, evt, array):
            if evt.phase == "release":
                array[400, 400] = 77
                raise ValueError("failed after mutation")
            array[0, 0] = 99
            return True

    dispatcher._handlers["brush"] = Handler()
    dispatcher(PointerEvent(phase="press", x=0, y=0, button=1, modifiers=0, pressure=1))
    dispatcher(PointerEvent(phase="release", x=0, y=0, button=0, modifiers=0, pressure=1))
    assert hints == [None]
    assert stack.undo()
    np.testing.assert_array_equal(doc.active_layer().image, 0)
    assert stack.redo()
    np.testing.assert_array_equal(doc.active_layer().image[400, 400], 77)


def test_commit_callback_failure_never_leaves_stale_regions():
    doc = _doc(16)
    state = ToolState()
    state.set_tool("brush")

    def fail():
        raise RuntimeError("cannot commit")

    dispatcher = ToolDispatcher(state, lambda: doc.active_layer().image,
                                DispatcherHooks(commit_undo=fail))
    dispatcher(PointerEvent(phase="press", x=5, y=5, button=1, modifiers=0, pressure=1))
    with pytest.raises(RuntimeError, match="cannot commit"):
        dispatcher(PointerEvent(phase="release", x=5, y=5, button=0,
                                modifiers=0, pressure=1))
    assert dispatcher.history_regions is None
