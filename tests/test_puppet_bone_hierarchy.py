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

from Imervue.puppet.bone_tree_dock import BoneTreeDock
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Deformer,
    Drawable,
    PuppetDocument,
)
from Imervue.puppet.runtime import (
    compose_drawable_vertices,
    topologically_sorted_deformers,
)


# QOpenGLWidget construction segfaults on the headless GitHub
# Actions Windows runner once the offscreen-GL pool is exhausted
# (see tests/conftest.py::skip_on_headless_ci). All tests in this
# file touch a real PuppetCanvas / PuppetWorkspace, so the whole
# module skips on CI; local runs cover them.
import os as _os_for_skip  # noqa: E402
import pytest as _pytest_for_skip  # noqa: E402

pytestmark = _pytest_for_skip.mark.skipif(
    _os_for_skip.environ.get("CI") == "true"
    or _os_for_skip.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
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


def test_canvas_selection_round_trips(qapp):
    """``set_selected_deformer`` stores the id and clears on ``None``,
    and ignores a redundant set so paintGL doesn't re-render for free."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    try:
        assert canvas.selected_deformer() is None
        canvas.set_selected_deformer("a")
        assert canvas.selected_deformer() == "a"
        canvas.set_selected_deformer(None)
        assert canvas.selected_deformer() is None
    finally:
        canvas.deleteLater()


def test_canvas_clear_selection_emits_signal(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    fired: list[int] = []
    canvas.selection_cleared.connect(lambda: fired.append(1))
    try:
        canvas.set_selected_deformer("a")
        canvas.clear_selection()
        assert canvas.selected_deformer() is None
        assert fired == [1]
        # Calling again should be a no-op — no double-fire.
        canvas.clear_selection()
        assert fired == [1]
    finally:
        canvas.deleteLater()


def test_canvas_set_selection_empty_string_is_clear(qapp):
    """Workspace connects ``deformer_selected(str)`` to
    ``set_selected_deformer`` directly. When the dock emits ``""`` to
    clear, set_selected_deformer must drop the overlay rather than
    leaving an empty-string selection in place."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    try:
        canvas.set_selected_deformer("a")
        canvas.set_selected_deformer("")
        assert canvas.selected_deformer() is None
    finally:
        canvas.deleteLater()


def test_dock_clear_selection_drops_tree_row(qapp):
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    dock = BoneTreeDock(canvas)
    try:
        # Select a row first
        first = dock.tree().topLevelItem(0)
        first.setSelected(True)
        assert dock.tree().selectedItems()
        dock.clear_selection()
        assert not dock.tree().selectedItems()
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_context_request_emits_empty_selection(qapp):
    """Right-clicking the tree should clear the row AND emit an
    empty deformer_selected so the canvas overlay clears too."""
    from PySide6.QtCore import QPoint
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    dock = BoneTreeDock(canvas)
    seen: list[str] = []
    dock.deformer_selected.connect(seen.append)
    try:
        # Pre-select something
        dock.tree().topLevelItem(0).setSelected(True)
        dock._on_tree_context_request(QPoint(0, 0))   # noqa: SLF001
        assert not dock.tree().selectedItems()
        assert "" in seen
    finally:
        dock.deleteLater()
        canvas.deleteLater()


def test_dock_selection_signal_drives_canvas(qapp):
    """Clicking a row in the dock emits ``deformer_selected`` —
    when the workspace wires that to ``canvas.set_selected_deformer``
    the canvas picks the same id up. We connect the signal manually
    here to mirror what the workspace does."""
    canvas = PuppetCanvas()
    canvas.load_document(_doc_with_two_deformers())
    dock = BoneTreeDock(canvas)
    try:
        dock.deformer_selected.connect(canvas.set_selected_deformer)
        # Simulate a click via the public signal — itemClicked needs a
        # QTreeWidgetItem we'd have to dig out of the model, so emit
        # the signal directly instead.
        dock.deformer_selected.emit("a")
        assert canvas.selected_deformer() == "a"
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
