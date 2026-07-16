"""Quick mask must restore the layer it was entered on, even across a tab switch.

The mask state lives on the workspace but the layer belongs to one document.
When the user switched to another tab (a different canvas/document) and exited,
the old exit path resolved against the ACTIVE document, failed its identity guard,
and dropped the saved original pixels -- leaving the masked layer as the red proxy
and losing the artwork. exit_quick_mask now restores against the owning document.

Driven on ContentOpsMixin methods with real PaintDocuments and a fake canvas --
no Qt widget is constructed, so it runs on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.paint.document import PaintDocument
from Imervue.paint.workspace_content import ContentOpsMixin


def _doc(fill: int) -> PaintDocument:
    document = PaintDocument()
    document.load_image(np.full((4, 4, 4), fill, dtype=np.uint8))
    return document


def _workspace(canvas_document):
    ws = SimpleNamespace(
        _quick_mask_state=None,
        _quick_mask_layer=None,
        _quick_mask_document=None,
        canvas=lambda: SimpleNamespace(
            document=lambda: canvas_document, update=lambda: None),
    )
    ws.is_quick_mask_active = lambda: ContentOpsMixin.is_quick_mask_active(ws)
    return ws


def test_exit_restores_owning_document_after_switch():
    owner = _doc(200)
    layer = owner.active_layer()
    original = layer.image.copy()

    ws = _workspace(canvas_document=owner)
    assert ContentOpsMixin.enter_quick_mask(ws) is True
    assert not np.array_equal(layer.image, original)   # now the red proxy buffer

    # Simulate switching to another tab: the active canvas shows a DIFFERENT doc.
    other = _doc(0)
    ws.canvas = lambda: SimpleNamespace(
        document=lambda: other, update=lambda: None)

    assert ContentOpsMixin.exit_quick_mask(ws) is True
    assert np.array_equal(layer.image, original)        # restored, not lost
    assert ws._quick_mask_state is None
    assert ws._quick_mask_document is None


def test_exit_without_active_mask_is_a_noop():
    ws = _workspace(canvas_document=_doc(0))
    assert ContentOpsMixin.exit_quick_mask(ws) is False


def test_exit_drops_safely_when_masked_layer_is_gone():
    owner = _doc(200)
    ws = _workspace(canvas_document=owner)
    ContentOpsMixin.enter_quick_mask(ws)
    # The tracked layer identity is no longer part of the owning document.
    ws._quick_mask_layer = SimpleNamespace(
        image=np.zeros((4, 4, 4), dtype=np.uint8))
    assert ContentOpsMixin.exit_quick_mask(ws) is False
    assert ws._quick_mask_state is None
