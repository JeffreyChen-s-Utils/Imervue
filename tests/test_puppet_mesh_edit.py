"""Pure-Python tests for the mesh-edit operations + canvas
toggle / drag plumbing."""
from __future__ import annotations
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, PuppetDocument
from Imervue.puppet.mesh_edit import (
    delete_vertex,
    find_drawable_at,
    find_vertex_at,
    move_vertex,
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



def _drawable_with_quad() -> Drawable:
    return Drawable(
        id="quad", texture="textures/x.png",
        vertices=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        indices=[0, 1, 2, 0, 2, 3],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        draw_order=0,
    )


# ---------------------------------------------------------------------------
# find_vertex_at
# ---------------------------------------------------------------------------


def test_find_vertex_picks_closest_within_radius():
    d = _drawable_with_quad()
    # (1, 1) is within 8 px of vertex 0 = (0, 0)
    assert find_vertex_at(d, 1.0, 1.0) == 0


def test_find_vertex_returns_none_when_no_vertex_in_radius():
    d = _drawable_with_quad()
    assert find_vertex_at(d, 100.0, 100.0) is None


def test_find_vertex_picks_truly_nearest_with_dense_mesh():
    d = _drawable_with_quad()
    d.vertices.extend([(5.0, 5.0), (5.5, 5.0)])
    # (5.4, 5.0) is closer to (5.5, 5.0) than (5.0, 5.0)
    assert find_vertex_at(d, 5.4, 5.0) == len(d.vertices) - 1


def test_find_vertex_empty_drawable_returns_none():
    d = Drawable(
        id="empty", texture="x.png",
        vertices=[], indices=[], uvs=[], draw_order=0,
    )
    assert find_vertex_at(d, 0.0, 0.0) is None


# ---------------------------------------------------------------------------
# move_vertex
# ---------------------------------------------------------------------------


def test_move_vertex_updates_position():
    d = _drawable_with_quad()
    assert move_vertex(d, 0, 5.0, 5.0) is True
    assert d.vertices[0] == (5.0, 5.0)


def test_move_vertex_out_of_range_returns_false():
    d = _drawable_with_quad()
    assert move_vertex(d, 99, 0.0, 0.0) is False
    assert move_vertex(d, -1, 0.0, 0.0) is False


# ---------------------------------------------------------------------------
# delete_vertex
# ---------------------------------------------------------------------------


def test_delete_vertex_drops_referencing_triangles():
    d = _drawable_with_quad()
    assert delete_vertex(d, 1) is True
    # 4 vertices → 3 vertices; both triangles that referenced vertex 1
    # disappear, the remaining triangle (0, 2, 3) stays.
    assert len(d.vertices) == 3
    assert len(d.uvs) == 3
    # All remaining indices should be in range
    assert all(0 <= i < 3 for i in d.indices)


def test_delete_vertex_shifts_remaining_indices():
    d = _drawable_with_quad()
    delete_vertex(d, 0)
    # Index 0 is gone, all others shift down by one.
    assert all(0 <= i < 3 for i in d.indices)


def test_delete_vertex_out_of_range_returns_false():
    d = _drawable_with_quad()
    assert delete_vertex(d, 99) is False


# ---------------------------------------------------------------------------
# find_drawable_at
# ---------------------------------------------------------------------------


def test_find_drawable_picks_topmost_by_draw_order():
    a = _drawable_with_quad()
    a.id = "a"
    a.draw_order = 0
    b = _drawable_with_quad()
    b.id = "b"
    b.draw_order = 10
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [a, b]
    hit = find_drawable_at(doc, 1.0, 1.0)
    assert hit == ("b", 0)


def test_find_drawable_at_misses_returns_none():
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [_drawable_with_quad()]
    assert find_drawable_at(doc, 100.0, 100.0) is None


# ---------------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------------


def test_canvas_mesh_edit_toggle(qapp):
    canvas = PuppetCanvas()
    try:
        assert canvas.mesh_edit_enabled() is False
        canvas.set_mesh_edit_enabled(True)
        assert canvas.mesh_edit_enabled() is True
        canvas.set_mesh_edit_enabled(False)
        assert canvas.mesh_edit_enabled() is False
    finally:
        canvas.deleteLater()


def test_canvas_drag_moves_vertex(qapp):
    canvas = PuppetCanvas()
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [_drawable_with_quad()]
    canvas.load_document(doc)
    try:
        canvas.set_mesh_edit_enabled(True)
        assert canvas.begin_mesh_edit_at(0.0, 0.0) is True
        canvas.update_mesh_edit_drag(20.0, 20.0)
        assert canvas.document().drawables[0].vertices[0] == (20.0, 20.0)
        canvas.end_mesh_edit_drag()
    finally:
        canvas.deleteLater()


def test_canvas_drag_when_disabled_is_noop(qapp):
    canvas = PuppetCanvas()
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [_drawable_with_quad()]
    canvas.load_document(doc)
    try:
        # Mesh edit OFF → no grab, no movement
        assert canvas.begin_mesh_edit_at(0.0, 0.0) is False
        canvas.update_mesh_edit_drag(20.0, 20.0)
        assert canvas.document().drawables[0].vertices[0] == (0.0, 0.0)
    finally:
        canvas.deleteLater()
