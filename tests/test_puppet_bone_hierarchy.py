"""Tests for the bone hierarchy editor + the runtime's FK
topological sort.

The Qt drag-and-drop path is exercised through the public
``reparent`` method so we don't need real drop events. The
FK ordering test asserts that ``compose_drawable_vertices`` runs
deformers in parent-first order even when the document lists them
in the reverse order.
"""
from __future__ import annotations

import numpy as np

from puppet.bone_tree_dock import BoneTreeDock
from puppet.canvas import PuppetCanvas
from puppet.document import (
    Deformer,
    Drawable,
    PuppetDocument,
)
from puppet.runtime import (
    compose_drawable_vertices,
    topologically_sorted_deformers,
)


def _drawable(id_: str = "x") -> Drawable:
    return Drawable(
        id=id_, texture="textures/x.png",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        draw_order=0,
    )


def _rotation_deformer(id_: str, *, parent: str | None, angle: float = 0.0,
                       anchor=(0.0, 0.0)) -> Deformer:
    return Deformer(
        id=id_, type="rotation", parent=parent,
        drawables=["x"],
        form={"anchor": list(anchor), "angle": angle},
    )


# ---------------------------------------------------------------------------
# topologically_sorted_deformers — pure helper
# ---------------------------------------------------------------------------


def test_topological_sort_root_first_when_doc_has_child_first():
    parent = _rotation_deformer("parent", parent=None)
    child = _rotation_deformer("child", parent="parent")
    grandchild = _rotation_deformer("gc", parent="child")
    # Document lists child-before-parent on purpose
    out = topologically_sorted_deformers([grandchild, child, parent])
    order = [d.id for d in out]
    assert order.index("parent") < order.index("child")
    assert order.index("child") < order.index("gc")


def test_topological_sort_handles_orphan_parent_id():
    """When a deformer's parent points at something that isn't in
    the list, the deformer still ends up in the output."""
    orphan = _rotation_deformer("loose", parent="missing")
    out = topologically_sorted_deformers([orphan])
    assert [d.id for d in out] == ["loose"]


def test_topological_sort_breaks_cycle_without_recursion_explosion():
    a = _rotation_deformer("a", parent="b")
    b = _rotation_deformer("b", parent="a")
    out = topologically_sorted_deformers([a, b])
    # Both deformers present, runtime stays defined (no stack overflow)
    assert {d.id for d in out} == {"a", "b"}


# ---------------------------------------------------------------------------
# Runtime — FK affects compose
# ---------------------------------------------------------------------------


def test_compose_runs_parent_rotation_before_child(qapp):
    """Two rotation deformers, child listed first in document order
    but with parent set. The compose output should equal what we get
    if we apply parent then child manually — proving the topological
    sort took effect."""
    drawable = _drawable()
    parent = _rotation_deformer(
        "parent", parent=None, angle=np.pi / 2, anchor=(0.0, 0.0),
    )
    child = _rotation_deformer(
        "child", parent="parent", angle=-np.pi / 2, anchor=(0.0, 0.0),
    )
    # Document order: child first
    out = compose_drawable_vertices(drawable, [child, parent], {})
    # parent (+90°) then child (-90°) = net 0° around origin → vertices
    # should be close to the originals (modulo float).
    expected = np.asarray(drawable.vertices, dtype=np.float32)
    assert np.allclose(out, expected, atol=1e-5)


# ---------------------------------------------------------------------------
# BoneTreeDock — reparent
# ---------------------------------------------------------------------------


def _doc_with_two_deformers() -> PuppetDocument:
    doc = PuppetDocument(size=(32, 32))
    doc.drawables = [_drawable()]
    doc.deformers = [
        _rotation_deformer("a", parent=None),
        _rotation_deformer("b", parent=None),
    ]
    return doc


def test_dock_empty_state_when_no_deformers(qapp):
    canvas = PuppetCanvas()
    dock = BoneTreeDock(canvas)
    try:
        canvas.load_document(PuppetDocument())
        assert dock.tree().topLevelItemCount() == 0
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_renders_deformers_under_their_parent(qapp):
    canvas = PuppetCanvas()
    doc = _doc_with_two_deformers()
    doc.deformers[1].parent = "a"   # b under a
    canvas.load_document(doc)
    dock = BoneTreeDock(canvas)
    try:
        tree = dock.tree()
        assert tree.topLevelItemCount() == 1
        root = tree.topLevelItem(0)
        assert root.text(0) == "a"
        assert root.childCount() == 1
        assert root.child(0).text(0) == "b"
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_reparent_updates_deformer_parent(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    dock = BoneTreeDock(canvas)
    try:
        fired = []
        dock.hierarchy_changed.connect(lambda: fired.append(1))
        ok = dock.reparent("b", "a")
        assert ok is True
        assert canvas.document().deformer("b").parent == "a"
        assert fired == [1]
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_reparent_rejects_cycle(qapp):
    """If a deformer is asked to become a child of one of its
    descendants, the dock must refuse — otherwise the topological
    sort can't terminate."""
    canvas = PuppetCanvas()
    doc = _doc_with_two_deformers()
    doc.deformers[1].parent = "a"   # b is a's child
    canvas.load_document(doc)
    dock = BoneTreeDock(canvas)
    try:
        # Now ask 'a' to become a child of 'b' — would form a cycle
        ok = dock.reparent("a", "b")
        assert ok is False
        # Original hierarchy intact
        assert canvas.document().deformer("a").parent is None
        assert canvas.document().deformer("b").parent == "a"
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_reparent_clears_parent_when_new_parent_is_none(qapp):
    canvas = PuppetCanvas()
    doc = _doc_with_two_deformers()
    doc.deformers[1].parent = "a"
    canvas.load_document(doc)
    dock = BoneTreeDock(canvas)
    try:
        dock.reparent("b", None)
        assert canvas.document().deformer("b").parent is None
    finally:
        dock.deleteLater()
        canvas.deleteLater()
