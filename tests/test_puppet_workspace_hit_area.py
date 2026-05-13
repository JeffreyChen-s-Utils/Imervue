"""Workspace-level integration test for hit-area click handling.

The canvas → workspace bridge plays the area's motion through the
motion dock and toggles its expression on the canvas. We instantiate a
real ``PuppetWorkspace`` under ``qapp`` and drive the canvas signal
directly so the test doesn't depend on Qt mouse events.
"""
from __future__ import annotations

from Imervue.puppet.document import (
    Drawable,
    Expression,
    ExpressionParam,
    HitArea,
    Motion,
    MotionSegment,
    MotionTrack,
    PuppetDocument,
)
from Imervue.puppet.workspace import PuppetWorkspace


def _doc_with_motion_and_expression() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        Drawable(
            id="head", texture="textures/x.png",
            vertices=[(10.0, 10.0), (50.0, 10.0), (50.0, 50.0), (10.0, 50.0)],
            indices=[0, 1, 2, 0, 2, 3],
            uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            draw_order=0,
        ),
    ]
    doc.motions = [
        Motion(
            name="wave",
            duration=1.0,
            tracks=[
                MotionTrack(
                    param_id="ParamAngleX",
                    segments=[
                        MotionSegment(type="linear", p0=(0.0, 0.0), p1=(1.0, 0.5)),
                    ],
                ),
            ],
        ),
    ]
    doc.expressions = [
        Expression(
            name="smile",
            params=[ExpressionParam(id="ParamMouthForm", value=0.5, mode="additive")],
        ),
    ]
    doc.hit_areas = [
        HitArea(id="head_tap", drawables=["head"], motion="wave"),
        HitArea(id="face_smile", drawables=["head"], expression="smile"),
    ]
    return doc


def test_hit_area_with_motion_selects_motion_in_dock(qapp):
    ws = PuppetWorkspace()
    try:
        ws.canvas().load_document(_doc_with_motion_and_expression())
        ws._on_hit_area_triggered("head_tap")   # noqa: SLF001
        player = ws._motion_dock.player()   # noqa: SLF001
        assert player.motion() is not None
        assert player.motion().name == "wave"
    finally:
        ws.deleteLater()


def test_hit_area_with_expression_toggles_canvas_stack(qapp):
    ws = PuppetWorkspace()
    try:
        ws.canvas().load_document(_doc_with_motion_and_expression())
        ws._on_hit_area_triggered("face_smile")   # noqa: SLF001
        assert "smile" in ws.canvas().active_expressions()
        # Second trigger should remove it
        ws._on_hit_area_triggered("face_smile")   # noqa: SLF001
        assert "smile" not in ws.canvas().active_expressions()
    finally:
        ws.deleteLater()


def test_unknown_hit_area_id_is_silent(qapp):
    """A signal carrying an id that doesn't match anything on the doc
    must not raise. (Defensive — the runtime stays defined even if a
    future feature emits stale ids.)"""
    ws = PuppetWorkspace()
    try:
        ws.canvas().load_document(_doc_with_motion_and_expression())
        ws._on_hit_area_triggered("does_not_exist")   # noqa: SLF001
    finally:
        ws.deleteLater()
