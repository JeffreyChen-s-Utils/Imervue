"""deepcopy(PaintDocument) must clone content, never the Qt listener wiring.

In a live workspace the layers dock and canvas always register bound-method
listeners on the active document, so page_dock's "Duplicate page"
(deepcopy(active.document)) crashed with TypeError: cannot pickle '<Dock>'
-- default deepcopy walks _listeners into the widget tree. Even when a
listener happened to survive copying, the clone would notify the ORIGINAL
page's widgets. __deepcopy__ now copies the layer stack / groups /
selections and starts the clone with no listeners and cold caches.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
from PySide6.QtWidgets import QWidget

from Imervue.paint.document import PaintDocument
from Imervue.paint.layer_model import LayerGroup
from Imervue.paint.paint_project import PaintProject, ProjectPage


class _Dock(QWidget):
    def refresh(self) -> None:   # python bound method, like docks/layers.py
        pass


def _doc_with_widget_listener(qapp):
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 100, dtype=np.uint8))
    dock = _Dock()
    doc.listen(dock.refresh)
    return doc, dock


def test_deepcopy_survives_qt_widget_listener(qapp):
    doc, dock = _doc_with_widget_listener(qapp)

    clone = deepcopy(doc)   # crashed pre-fix: cannot pickle '_Dock' object

    assert clone._listeners == []          # clone never notifies original widgets
    assert clone.layer_count == 1
    dock.deleteLater()


def test_deepcopy_clones_content_independently(qapp):
    doc, dock = _doc_with_widget_listener(qapp)
    doc.layer_at(0).name = "ink"
    doc._groups["g"] = LayerGroup(name="g", opacity=0.5)
    doc._named_selections["sel"] = np.ones((4, 4), dtype=np.uint8)
    doc._reference_layer_index = 0

    clone = deepcopy(doc)

    # Content carried over...
    assert clone.layer_at(0).name == "ink"
    assert clone._groups["g"].opacity == pytest.approx(0.5)
    assert clone._named_selections["sel"].sum() == 16
    assert clone._reference_layer_index == 0
    assert clone.active_layer_index() == doc.active_layer_index()
    # ...but fully independent: pixel edits on the clone don't leak back.
    clone.layer_at(0).image[:] = 0
    assert int(doc.layer_at(0).image[0, 0, 0]) == 100
    clone._named_selections["sel"][:] = 0
    assert doc._named_selections["sel"].sum() == 16
    dock.deleteLater()


def test_deepcopy_starts_with_cold_composite_cache(qapp):
    doc, dock = _doc_with_widget_listener(qapp)
    doc.composite()                          # build the original's cache
    assert doc._composite_cache is not None

    clone = deepcopy(doc)
    assert clone._composite_cache is None    # cold, rebuilt on demand
    assert clone._composite_dirty_rect is None
    dock.deleteLater()


def test_page_dock_duplicate_flow_with_listened_document(qapp):
    """End-to-end: duplicating the active page of a real project must work
    while the document has a live Qt-widget listener (the crash scenario)."""
    doc, dock = _doc_with_widget_listener(qapp)
    project = PaintProject(pages=[ProjectPage(document=doc, name="Page 1")])

    clone_page = ProjectPage(
        document=deepcopy(project.active_page().document),
        name=f"{project.active_page().name} copy",
    )
    project.add_page(clone_page)

    assert project.page_count == 2
    assert project.pages[1].name == "Page 1 copy"
    assert project.pages[1].document is not doc
    assert project.pages[1].document.layer_count == 1
    dock.deleteLater()
