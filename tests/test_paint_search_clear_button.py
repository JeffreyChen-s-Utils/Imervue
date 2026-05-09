"""Tests for the search-line clear-button affordance — phase 36b.

The layer dock and material library now expose Qt's built-in clear
button on their search field (the small "×" that appears on the right
when text is entered). Without it the artist had to delete a long
query character by character, which became annoying once the layer
list grew past a handful of layers.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QLineEdit

from Imervue.paint.dock_panels import LayerDock, MaterialDock
from Imervue.paint.document import PaintDocument


@pytest.fixture
def layer_dock(qapp):
    doc = PaintDocument()
    doc.load_image(np.zeros((24, 24, 4), dtype=np.uint8))
    dock = LayerDock(doc)
    yield dock
    dock.deleteLater()


def test_layer_dock_search_has_clear_button(layer_dock):
    edit = layer_dock.findChild(QLineEdit)
    assert edit is not None
    assert edit.isClearButtonEnabled()


def test_layer_dock_search_has_tooltip(layer_dock):
    edit = layer_dock.findChild(QLineEdit)
    assert edit is not None
    assert edit.toolTip()


def test_material_dock_search_has_clear_button(qapp):
    dock = MaterialDock()
    try:
        edit = dock.findChild(QLineEdit)
        assert edit is not None
        assert edit.isClearButtonEnabled()
    finally:
        dock.deleteLater()


def test_material_dock_search_has_tooltip(qapp):
    dock = MaterialDock()
    try:
        edit = dock.findChild(QLineEdit)
        assert edit is not None
        assert edit.toolTip()
    finally:
        dock.deleteLater()
