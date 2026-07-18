"""Tests for three paint state-desync fixes: layer-dock listener leak, quick-mask
restore-by-identity, and the undo gesture flag surviving a mid-stroke tool switch.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.paint.tool_dispatcher import ToolDispatcher


# ---------------------------------------------------------------------------
# LayerDock.set_document — drop the previous document's listener
# ---------------------------------------------------------------------------

def test_set_document_unsubscribes_the_previous_document(qapp):
    from Imervue.paint.dock_panels import LayerDock
    from Imervue.paint.document import PaintDocument

    doc_a = PaintDocument()
    doc_a.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
    dock = LayerDock(doc_a)
    try:
        unsubscribed: list = []
        dock._unsubscribe = lambda: unsubscribed.append(True)  # noqa: SLF001
        doc_b = PaintDocument()
        doc_b.load_image(np.zeros((8, 8, 4), dtype=np.uint8))
        dock.set_document(doc_b)
        assert unsubscribed == [True]        # previous listener released
    finally:
        dock.deleteLater()


# ---------------------------------------------------------------------------
# Undo gesture flag — commit on release even after a mid-stroke tool switch
# ---------------------------------------------------------------------------

def _dispatcher_fake(pending):
    commits: list = []
    fake = SimpleNamespace(
        _MUTATING_TOOLS=ToolDispatcher._MUTATING_TOOLS,
        _SINGLE_SHOT_TOOLS=ToolDispatcher._SINGLE_SHOT_TOOLS,
        _gesture_pending_commit=pending,
        _commit_undo=lambda: commits.append(True),
    )
    return fake, commits


def test_pending_gesture_commits_on_release_after_switch_to_non_mutating_tool():
    fake, commits = _dispatcher_fake(pending=True)
    evt = SimpleNamespace(phase="release")
    # The user switched to a non-mutating tool (hand) before releasing.
    ToolDispatcher._maybe_commit_undo(fake, "hand", evt, handled=False)
    assert commits == [True]
    assert fake._gesture_pending_commit is False


def test_gesture_press_then_release_commits_once():
    tool = next(iter(ToolDispatcher._MUTATING_TOOLS
                     - ToolDispatcher._SINGLE_SHOT_TOOLS))
    fake, commits = _dispatcher_fake(pending=False)
    ToolDispatcher._maybe_commit_undo(
        fake, tool, SimpleNamespace(phase="press"), handled=True)
    assert fake._gesture_pending_commit is True
    ToolDispatcher._maybe_commit_undo(
        fake, tool, SimpleNamespace(phase="release"), handled=True)
    assert commits == [True]
    assert fake._gesture_pending_commit is False


# ---------------------------------------------------------------------------
# Quick-mask exit — restore into the stored layer, not the same index
# ---------------------------------------------------------------------------

def test_exit_quick_mask_restores_the_stored_layer_after_reorder(qapp):
    from Imervue.paint.quick_mask import enter_mode
    from Imervue.paint.workspace_content import ContentOpsMixin

    state = enter_mode(np.zeros((4, 4, 4), dtype=np.uint8), None, layer_index=0)
    target = SimpleNamespace(image=state.buffer)       # was masked at index 0
    other = SimpleNamespace(image=np.zeros((4, 4, 4), dtype=np.uint8))
    other_original = other.image
    # A layer was inserted, so the target now sits at index 1, not 0.
    document = SimpleNamespace(
        layers=lambda: [other, target],
        layer_count=2,
        invalidate_composite=lambda: None,
        set_selection=lambda s: None,
    )
    canvas = SimpleNamespace(
        document=lambda: document,
        set_selection=lambda s: None,
        update=lambda: None,
    )
    host = SimpleNamespace(
        _quick_mask_state=state,
        _quick_mask_layer=target,
        _quick_mask_document=document,
        is_quick_mask_active=lambda: True,
        canvas=lambda: canvas,
    )
    assert ContentOpsMixin.exit_quick_mask(host) is True
    assert target.image is not state.buffer      # restored into the RIGHT layer
    assert other.image is other_original          # the index-0 layer untouched


def test_exit_quick_mask_drops_state_when_layer_removed(qapp):
    from Imervue.paint.quick_mask import enter_mode
    from Imervue.paint.workspace_content import ContentOpsMixin

    state = enter_mode(np.zeros((4, 4, 4), dtype=np.uint8), None, layer_index=0)
    removed_layer = SimpleNamespace(image=state.buffer)
    document = SimpleNamespace(layers=lambda: [], layer_count=0,
                              invalidate_composite=lambda: None)
    canvas = SimpleNamespace(document=lambda: document,
                             set_selection=lambda s: None, update=lambda: None)
    host = SimpleNamespace(
        _quick_mask_state=state,
        _quick_mask_layer=removed_layer,
        is_quick_mask_active=lambda: True,
        canvas=lambda: canvas,
    )
    assert ContentOpsMixin.exit_quick_mask(host) is False
    assert host._quick_mask_state is None
    assert host._quick_mask_layer is None
