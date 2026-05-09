"""Tests for the LayerDock lock-alpha button — phase 35b.

The button surfaces ``Layer.lock_alpha`` so the artist doesn't have to
reach for a context menu (or, before this, edit the saved settings)
to toggle Photoshop's "Transparency lock". Coverage:

* Toggle propagates to the active layer's ``lock_alpha`` field.
* The button reflects the current layer's state when refreshed.
* Switching to a layer with ``lock_alpha=True`` lights the button.
* The button disables when the document has no active layer.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QToolButton

from Imervue.paint.dock_panels import LayerDock
from Imervue.paint.document import PaintDocument


@pytest.fixture
def doc(qapp):
    document = PaintDocument()
    document.load_image(np.zeros((24, 24, 4), dtype=np.uint8))
    return document


@pytest.fixture
def dock(qapp, doc):
    panel = LayerDock(doc)
    yield panel
    panel.deleteLater()


def _lock_button(dock: LayerDock) -> QToolButton:
    return next(
        b for b in dock.findChildren(QToolButton)
        if "α" in b.text()
    )


def test_lock_alpha_button_starts_unchecked(dock, doc):
    btn = _lock_button(dock)
    assert btn.isCheckable()
    assert not btn.isChecked()


def test_toggle_propagates_to_active_layer(dock, doc):
    btn = _lock_button(dock)
    btn.setChecked(True)
    assert doc.active_layer().lock_alpha is True
    btn.setChecked(False)
    assert doc.active_layer().lock_alpha is False


def test_refresh_reflects_existing_lock(qapp, doc):
    """Build a fresh dock against a document whose active layer is
    already lock-alpha; the button must come up checked without the
    user having to toggle it."""
    layer = doc.active_layer()
    layer.lock_alpha = True
    dock = LayerDock(doc)
    try:
        assert _lock_button(dock).isChecked()
    finally:
        dock.deleteLater()


def test_button_disabled_when_no_active_layer(qapp):
    """A bare PaintDocument with no image has no active layer; the
    lock button should disable rather than crash on toggle."""
    empty_doc = PaintDocument()
    dock = LayerDock(empty_doc)
    try:
        btn = _lock_button(dock)
        assert not btn.isEnabled()
    finally:
        dock.deleteLater()


def test_toggle_emits_through_set_layer_lock_alpha(dock, doc, monkeypatch):
    """The dock should route the toggle through ``set_layer_lock_alpha``
    on the document — that's the canonical path which fires the
    listener notification, so the rest of the workspace updates."""
    captured = {}
    original = doc.set_layer_lock_alpha

    def spy(index, *, lock_alpha):
        captured["index"] = index
        captured["lock_alpha"] = lock_alpha
        return original(index, lock_alpha=lock_alpha)

    monkeypatch.setattr(doc, "set_layer_lock_alpha", spy)
    btn = _lock_button(dock)
    btn.setChecked(True)
    assert captured["lock_alpha"] is True
    assert captured["index"] >= 0
