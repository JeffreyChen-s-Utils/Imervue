"""Tests for HitArea — pure hit-test math, round-trip through the
``.puppet`` archive IO, and the canvas signal that fires when the
user clicks inside one.
"""
from __future__ import annotations

import numpy as np

from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document import Drawable, HitArea, PuppetDocument
from Imervue.puppet.document_io import from_zip_bytes, to_zip_bytes
from Imervue.puppet.hit_test import hit_area_bbox, hit_test


def _square_drawable(
    drawable_id: str,
    x0: float, y0: float, x1: float, y1: float,
    draw_order: int = 0,
) -> Drawable:
    return Drawable(
        id=drawable_id,
        texture="textures/x.png",
        vertices=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        indices=[0, 1, 2, 0, 2, 3],
        uvs=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        draw_order=draw_order,
    )


def _doc_with_one_area() -> PuppetDocument:
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [_square_drawable("head", 10.0, 10.0, 50.0, 50.0)]
    doc.hit_areas = [
        HitArea(id="head_area", drawables=["head"], motion="tap_head"),
    ]
    return doc


# ---------------------------------------------------------------------------
# hit_test — happy / miss / edges
# ---------------------------------------------------------------------------


def test_hit_inside_bbox_returns_area_id():
    doc = _doc_with_one_area()
    assert hit_test(doc, 30.0, 30.0) == "head_area"


def test_hit_outside_bbox_returns_none():
    doc = _doc_with_one_area()
    assert hit_test(doc, 80.0, 80.0) is None


def test_hit_on_corner_counts_as_inside():
    """Boundary inclusive — clicks exactly on the AABB corner should
    still resolve so the user doesn't get a dead pixel right at the
    edge of the visible drawable."""
    doc = _doc_with_one_area()
    assert hit_test(doc, 10.0, 10.0) == "head_area"
    assert hit_test(doc, 50.0, 50.0) == "head_area"


def test_no_hit_areas_returns_none():
    doc = PuppetDocument(size=(100, 100))
    assert hit_test(doc, 50.0, 50.0) is None


def test_hit_area_missing_drawable_is_skipped():
    """A hit area pointing at a non-existent drawable can't form a
    bounding box — the hit test should silently skip it rather than
    crashing."""
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [_square_drawable("head", 10.0, 10.0, 50.0, 50.0)]
    doc.hit_areas = [HitArea(id="ghost", drawables=["does_not_exist"])]
    assert hit_test(doc, 30.0, 30.0) is None


def test_overlapping_areas_pick_topmost_draw_order():
    doc = PuppetDocument(size=(100, 100))
    doc.drawables = [
        _square_drawable("back", 0.0, 0.0, 100.0, 100.0, draw_order=0),
        _square_drawable("front", 20.0, 20.0, 80.0, 80.0, draw_order=10),
    ]
    doc.hit_areas = [
        HitArea(id="back_area", drawables=["back"]),
        HitArea(id="front_area", drawables=["front"]),
    ]
    # Point lies in both areas — front should win because its drawable
    # has the higher draw_order.
    assert hit_test(doc, 40.0, 40.0) == "front_area"


def test_hit_test_uses_deformed_vertices_when_supplied():
    """If the runtime has translated the drawable away from its rest
    position, the hit test should follow the deformed AABB rather than
    the rest-pose AABB."""
    doc = _doc_with_one_area()
    deformed = {
        "head": np.array(
            [[60.0, 60.0], [90.0, 60.0], [90.0, 90.0], [60.0, 90.0]],
            dtype=np.float32,
        ),
    }
    assert hit_test(doc, 30.0, 30.0, deformed_vertices=deformed) is None
    assert hit_test(doc, 75.0, 75.0, deformed_vertices=deformed) == "head_area"


def test_hit_area_bbox_helper_matches_drawable_extent():
    doc = _doc_with_one_area()
    bbox = hit_area_bbox(doc, doc.hit_areas[0])
    assert bbox == (10.0, 10.0, 50.0, 50.0)


# ---------------------------------------------------------------------------
# Document IO round-trip
# ---------------------------------------------------------------------------


def test_hit_areas_round_trip_through_zip():
    doc = _doc_with_one_area()
    doc.hit_areas.append(
        HitArea(id="body_area", drawables=["head"], expression="smile"),
    )
    payload = to_zip_bytes(doc)
    restored = from_zip_bytes(payload)
    assert [h.id for h in restored.hit_areas] == ["head_area", "body_area"]
    assert restored.hit_areas[0].motion == "tap_head"
    assert restored.hit_areas[0].expression is None
    assert restored.hit_areas[1].motion is None
    assert restored.hit_areas[1].expression == "smile"


def test_document_without_hit_areas_serialises_clean():
    """An older puppet without hit_areas must still round-trip — the
    field is optional and additive."""
    doc = PuppetDocument(size=(64, 64))
    doc.drawables = [_square_drawable("x", 0.0, 0.0, 1.0, 1.0)]
    payload = to_zip_bytes(doc)
    restored = from_zip_bytes(payload)
    assert restored.hit_areas == []


# ---------------------------------------------------------------------------
# Canvas signal
# ---------------------------------------------------------------------------


def test_canvas_emits_signal_when_click_hits_area(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_one_area())
        seen: list[str] = []
        canvas.hit_area_triggered.connect(seen.append)
        result = canvas.try_trigger_hit_area_at(30.0, 30.0)
        assert result == "head_area"
        assert seen == ["head_area"]
    finally:
        canvas.deleteLater()


def test_canvas_does_not_emit_when_click_misses(qapp):
    canvas = PuppetCanvas()
    try:
        canvas.load_document(_doc_with_one_area())
        seen: list[str] = []
        canvas.hit_area_triggered.connect(seen.append)
        result = canvas.try_trigger_hit_area_at(80.0, 80.0)
        assert result is None
        assert seen == []
    finally:
        canvas.deleteLater()


def test_canvas_no_emit_when_document_has_no_hit_areas(qapp):
    canvas = PuppetCanvas()
    try:
        # Document without hit areas
        doc = PuppetDocument(size=(64, 64))
        doc.drawables = [_square_drawable("x", 0.0, 0.0, 50.0, 50.0)]
        canvas.load_document(doc)
        seen: list[str] = []
        canvas.hit_area_triggered.connect(seen.append)
        assert canvas.try_trigger_hit_area_at(10.0, 10.0) is None
        assert seen == []
    finally:
        canvas.deleteLater()
