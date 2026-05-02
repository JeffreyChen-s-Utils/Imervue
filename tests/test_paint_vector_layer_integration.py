"""Tests for vector layer compositing + pen-commit routing.

The :mod:`Imervue.paint.vector_layer` rasterisation API is already
exercised in its own test module; this file pins the integration
points the user actually touches:

* The compositor calls ``realise_vector_layer`` so vector strokes
  appear in the composite without a manual realise step.
* The pen-commit path appends a :class:`VectorStroke` (rather than
  baking pixels) when the active layer is a vector layer.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.bezier_path import BezierPath, PathNode
from Imervue.paint.compositing import composite_stack
from Imervue.paint.document import Layer
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.paint.pen_commit import commit_pen_path
from Imervue.paint.vector_layer import VectorLayerData, VectorStroke
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Composite renders vector strokes
# ---------------------------------------------------------------------------


def test_composite_realises_vector_strokes_into_layer_image():
    """A vector layer with strokes but a blank cached image should
    have its image populated by the compositor before blending."""
    h, w = 32, 32
    data = VectorLayerData()
    data.add(VectorStroke(
        points=((4.0, 16.0), (28.0, 16.0)), width=4.0,
        color=(255, 0, 0, 255),
    ))
    layer = Layer(
        name="vec",
        image=np.zeros((h, w, 4), dtype=np.uint8),
        vector_data=data,
    )
    out = composite_stack([layer], (h, w))
    # The horizontal stroke at y=16 should leave at least one
    # opaque red pixel along the central row.
    central_row = out[16]
    red_pixels = (
        (central_row[..., 0] == 255)
        & (central_row[..., 1] == 0)
        & (central_row[..., 2] == 0)
        & (central_row[..., 3] > 0)
    )
    assert red_pixels.any()


def test_composite_respects_vector_cache_invalidation():
    """Adding a stroke after a first composite call should re-render."""
    h, w = 24, 24
    layer = Layer(
        name="vec",
        image=np.zeros((h, w, 4), dtype=np.uint8),
        vector_data=VectorLayerData(),
    )
    first = composite_stack([layer], (h, w))
    assert first.sum() == 0   # empty data → empty composite
    layer.vector_data.add(VectorStroke(
        points=((6.0, 12.0), (18.0, 12.0)), width=3.0,
        color=(0, 0, 255, 255),
    ))
    # Vector layer cache needs invalidating so the compositor sees
    # the new stroke. ``add`` already invalidates internally.
    second = composite_stack([layer], (h, w))
    assert second.sum() > 0


# ---------------------------------------------------------------------------
# Pen-commit routes to vector_data
# ---------------------------------------------------------------------------


def test_pen_commit_to_vector_layer_appends_vector_stroke(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.add_vector_layer()  # active layer is now vector
        layer = document.active_layer()
        assert layer.vector_data is not None
        assert layer.vector_data.strokes == []
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 10.0)),
                PathNode(anchor=(40.0, 30.0)),
                PathNode(anchor=(50.0, 50.0)),
            ],
        )
        ws.state().set_brush(size=6)
        ws.state().set_foreground((128, 64, 32))
        committed = commit_pen_path(ws)
        assert committed is True
        # The vector layer now has one stroke with three anchor points.
        assert len(layer.vector_data.strokes) == 1
        stroke = layer.vector_data.strokes[0]
        assert len(stroke.points) == 3
        assert stroke.color[:3] == (128, 64, 32)
        assert stroke.width == pytest.approx(6.0)
    finally:
        ws.deleteLater()


def test_pen_commit_to_raster_layer_still_rasterises(qapp):
    """The raster path must keep working — committing on a normal
    layer must mutate pixels, not vector data."""
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        layer = document.active_layer()
        assert layer.vector_data is None
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(8.0, 30.0)),
                PathNode(anchor=(48.0, 30.0)),
            ],
        )
        ws.state().set_brush(size=6)
        ws.state().set_foreground((255, 0, 0))
        before = layer.image.copy()
        committed = commit_pen_path(ws)
        assert committed is True
        assert (layer.image != before).any()
    finally:
        ws.deleteLater()


def test_pen_commit_clears_path_for_both_layer_types(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.add_vector_layer()
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(10.0, 10.0)),
                PathNode(anchor=(20.0, 20.0)),
            ],
        )
        commit_pen_path(ws)
        assert ws._bezier_pen_path.nodes == []  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_pen_commit_invalidates_composite_for_vector_layer(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document.add_vector_layer()
        document.composite()
        assert document._composite_cache is not None  # noqa: SLF001
        ws._bezier_pen_path = BezierPath(  # noqa: SLF001
            nodes=[
                PathNode(anchor=(5.0, 5.0)),
                PathNode(anchor=(25.0, 25.0)),
            ],
        )
        commit_pen_path(ws)
        assert document._composite_cache is None  # noqa: SLF001
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Add-vector-layer Layer-menu entry already exists; verify it ends
# up wired the way the pen-commit path expects.
# ---------------------------------------------------------------------------


def test_layer_menu_add_vector_layer_creates_vector_data(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._layer_menu_bridge   # noqa: SLF001
        before = ws.canvas().document().layer_count
        bridge.add_vector_layer()
        document = ws.canvas().document()
        assert document.layer_count == before + 1
        assert document.active_layer().vector_data is not None
    finally:
        ws.deleteLater()
