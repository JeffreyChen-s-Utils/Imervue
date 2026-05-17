"""Tests for expression overlay + pose visibility — runtime math
plus canvas integration.
"""
from __future__ import annotations
import pytest

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import (
    Drawable,
    Expression,
    ExpressionParam,
    PoseGroup,
    PuppetDocument,
)
from Imervue.puppet.runtime import (
    apply_expression,
    apply_expressions,
    resolve_pose_visibility,
)

from _qt_skip import pytestmark  # noqa: E402,F401


# ---------------------------------------------------------------------------
# apply_expression — modes
# ---------------------------------------------------------------------------


def test_expression_additive_mode_sums_with_base():
    expr = Expression(
        name="smile",
        params=[ExpressionParam(id="A", value=0.3, mode="additive")],
    )
    out = apply_expression({"A": 1.0, "B": 2.0}, expr)
    assert out["A"] == pytest.approx(1.3)
    assert out["B"] == pytest.approx(2.0)


def test_expression_multiply_mode_scales_base():
    expr = Expression(
        name="x",
        params=[ExpressionParam(id="A", value=2.0, mode="multiply")],
    )
    assert apply_expression({"A": 1.5}, expr)["A"] == pytest.approx(3.0)


def test_expression_overwrite_mode_replaces_base():
    expr = Expression(
        name="x",
        params=[ExpressionParam(id="A", value=9.0, mode="overwrite")],
    )
    assert apply_expression({"A": 1.0}, expr)["A"] == pytest.approx(9.0)


def test_expression_introduces_param_not_in_base():
    expr = Expression(
        name="x",
        params=[ExpressionParam(id="NEW", value=5.0, mode="overwrite")],
    )
    assert apply_expression({}, expr)["NEW"] == pytest.approx(5.0)


def test_expression_does_not_mutate_input():
    base = {"A": 1.0}
    expr = Expression(
        name="x",
        params=[ExpressionParam(id="A", value=2.0, mode="additive")],
    )
    apply_expression(base, expr)
    assert base == {"A": 1.0}


def test_apply_expressions_chains_in_list_order():
    base = {"A": 0.0}
    e1 = Expression(name="e1", params=[
        ExpressionParam(id="A", value=1.0, mode="additive"),
    ])
    e2 = Expression(name="e2", params=[
        ExpressionParam(id="A", value=2.0, mode="additive"),
    ])
    assert apply_expressions(base, [e1, e2])["A"] == pytest.approx(3.0)


def test_apply_expressions_with_empty_list_returns_copy():
    base = {"A": 1.0}
    out = apply_expressions(base, [])
    assert out == base
    assert out is not base


# ---------------------------------------------------------------------------
# Pose visibility
# ---------------------------------------------------------------------------


def _doc_with_pose() -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    for did in ("sword", "bow", "fist", "background"):
        doc.drawables.append(
            Drawable(
                id=did, texture="textures/x.png",
                vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
                draw_order=0,
            ),
        )
    doc.pose_groups = [
        PoseGroup(id="weapons", drawables=["sword", "bow", "fist"]),
    ]
    return doc


def test_pose_default_picks_first_member_when_none_active():
    doc = _doc_with_pose()
    out = resolve_pose_visibility(doc, {})
    assert out["sword"] is True
    assert out["bow"] is False
    assert out["fist"] is False
    assert out["background"] is True   # not in any group


def test_pose_active_member_shown_others_hidden():
    doc = _doc_with_pose()
    out = resolve_pose_visibility(doc, {"weapons": "bow"})
    assert out["bow"] is True
    assert out["sword"] is False
    assert out["fist"] is False


def test_pose_invalid_active_falls_back_to_first_member():
    doc = _doc_with_pose()
    out = resolve_pose_visibility(doc, {"weapons": "ghost"})
    assert out["sword"] is True


def test_pose_authored_invisible_drawable_outside_group_stays_hidden():
    doc = _doc_with_pose()
    doc.drawables[3].visible = False   # background
    out = resolve_pose_visibility(doc, {})
    assert out["background"] is False


# ---------------------------------------------------------------------------
# Canvas integration
# ---------------------------------------------------------------------------


def _canvas_with_doc(qapp_):
    doc = _doc_with_pose()
    doc.expressions = [
        Expression(
            name="smile",
            params=[ExpressionParam(id="A", value=0.5, mode="overwrite")],
        ),
    ]
    canvas = PuppetCanvas()
    canvas.load_document(doc)
    return canvas


def test_canvas_add_expression_changes_active_list(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        assert canvas.add_expression("smile") is True
        assert canvas.active_expressions() == ["smile"]
        # Adding the same one twice is a no-op
        assert canvas.add_expression("smile") is False
    finally:
        canvas.deleteLater()


def test_canvas_remove_expression_clears_it(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        canvas.add_expression("smile")
        assert canvas.remove_expression("smile") is True
        assert canvas.active_expressions() == []
        assert canvas.remove_expression("smile") is False
    finally:
        canvas.deleteLater()


def test_canvas_add_unknown_expression_returns_false(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        assert canvas.add_expression("ghost") is False
    finally:
        canvas.deleteLater()


def test_canvas_set_pose_active_updates_visibility(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        assert canvas.set_pose_active("weapons", "bow") is True
        viz = canvas.visibility()
        assert viz["bow"] is True
        assert viz["sword"] is False
    finally:
        canvas.deleteLater()


def test_canvas_set_pose_invalid_drawable_returns_false(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        assert canvas.set_pose_active("weapons", "ghost") is False
        # Active pose unchanged
        assert canvas.active_pose() == {}
    finally:
        canvas.deleteLater()


def test_canvas_set_pose_unknown_group_returns_false(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        assert canvas.set_pose_active("ghost_group", "sword") is False
    finally:
        canvas.deleteLater()


def test_canvas_load_document_clears_expression_and_pose(qapp):
    canvas = _canvas_with_doc(qapp)
    try:
        canvas.add_expression("smile")
        canvas.set_pose_active("weapons", "bow")
        canvas.load_document(_doc_with_pose())   # fresh doc, no expressions
        assert canvas.active_expressions() == []
        assert canvas.active_pose() == {}
    finally:
        canvas.deleteLater()
