"""Tests for vector strokes and the non-destructive layer wrapper."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.vector_layer import (
    DEFAULT_VECTOR_COLOR,
    DEFAULT_VECTOR_WIDTH,
    VectorLayerData,
    VectorStroke,
    rasterise_strokes,
    realise_vector_layer,
)


# ---------------------------------------------------------------------------
# VectorStroke construction
# ---------------------------------------------------------------------------


def test_vector_stroke_defaults():
    stroke = VectorStroke(points=((0.0, 0.0), (10.0, 10.0)))
    assert stroke.width == DEFAULT_VECTOR_WIDTH
    assert stroke.color == DEFAULT_VECTOR_COLOR
    assert stroke.opacity == 1.0


def test_vector_stroke_rejects_zero_width():
    with pytest.raises(ValueError, match="width must be positive"):
        VectorStroke(points=((0.0, 0.0),), width=0.0)


def test_vector_stroke_rejects_negative_width():
    with pytest.raises(ValueError, match="width must be positive"):
        VectorStroke(points=((0.0, 0.0),), width=-2.0)


def test_vector_stroke_rejects_out_of_range_opacity():
    with pytest.raises(ValueError, match=r"opacity must be in \[0, 1\]"):
        VectorStroke(points=((0.0, 0.0),), opacity=1.5)


def test_vector_stroke_rejects_malformed_color():
    with pytest.raises(ValueError, match="color must be a 4-tuple"):
        VectorStroke(points=((0.0, 0.0),), color=(255, 0, 0))


def test_vector_stroke_accepts_empty_point_list():
    """Empty strokes are valid carriers (e.g. just-created, no clicks
    yet) — the rasteriser must skip them rather than crash."""
    stroke = VectorStroke(points=())
    canvas = np.zeros((10, 10, 4), dtype=np.uint8)
    rasterise_strokes(canvas, [stroke])
    assert (canvas == 0).all()


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_vector_stroke_round_trip_via_dict():
    original = VectorStroke(
        points=((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)),
        width=8.0,
        color=(100, 200, 50, 255),
        opacity=0.7,
    )
    rebuilt = VectorStroke.from_dict(original.to_dict())
    assert rebuilt == original


def test_vector_stroke_from_dict_clamps_color():
    rebuilt = VectorStroke.from_dict({
        "points": [[0, 0]], "color": [-50, 300, 100, 999],
    })
    assert rebuilt.color == (0, 255, 100, 255)


def test_vector_stroke_from_dict_clamps_opacity():
    rebuilt = VectorStroke.from_dict({"points": [[0, 0]], "opacity": 99.0})
    assert rebuilt.opacity == 1.0


def test_vector_stroke_from_dict_drops_malformed_points():
    rebuilt = VectorStroke.from_dict({
        "points": [[0, 0], "garbage", [1, 2, 3], [3, 4]],
    })
    assert rebuilt.points == ((0.0, 0.0), (3.0, 4.0))


# ---------------------------------------------------------------------------
# Rasterisation
# ---------------------------------------------------------------------------


def test_rasterise_single_point_paints_centre():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    rasterise_strokes(canvas, [
        VectorStroke(points=((10.0, 10.0),), width=4.0, color=(255, 0, 0, 255)),
    ])
    # Centre alpha > 0.
    assert canvas[10, 10, 3] > 0


def test_rasterise_polyline_paints_along_path():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    rasterise_strokes(canvas, [
        VectorStroke(
            points=((2.0, 10.0), (18.0, 10.0)), width=3.0,
            color=(0, 200, 0, 255),
        ),
    ])
    # Painted along y=10 between x=2 and x=18.
    painted_mask = canvas[..., 3] > 0
    assert painted_mask[10, 5]
    assert painted_mask[10, 15]
    # Far away from the stroke remains untouched.
    assert not painted_mask[2, 2]


def test_rasterise_rejects_non_rgba_canvas():
    canvas = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        rasterise_strokes(canvas, [VectorStroke(points=((0.0, 0.0),))])


def test_rasterise_multiple_strokes_composite():
    canvas = np.zeros((20, 20, 4), dtype=np.uint8)
    rasterise_strokes(canvas, [
        VectorStroke(points=((5.0, 10.0),), width=4.0, color=(255, 0, 0, 255)),
        VectorStroke(points=((15.0, 10.0),), width=4.0, color=(0, 0, 255, 255)),
    ])
    # Two distinct dabs, neither overlapping.
    assert canvas[10, 5, 0] > 0   # red
    assert canvas[10, 15, 2] > 0  # blue


# ---------------------------------------------------------------------------
# VectorLayerData
# ---------------------------------------------------------------------------


def test_vector_layer_data_starts_empty():
    data = VectorLayerData()
    assert data.strokes == []


def test_vector_layer_data_add_appends():
    data = VectorLayerData()
    s = VectorStroke(points=((1.0, 1.0),))
    data.add(s)
    assert data.strokes == [s]


def test_vector_layer_data_remove_drops_index():
    data = VectorLayerData()
    s1 = VectorStroke(points=((0.0, 0.0),))
    s2 = VectorStroke(points=((10.0, 10.0),))
    data.add(s1)
    data.add(s2)
    assert data.remove(0)
    assert data.strokes == [s2]


def test_vector_layer_data_remove_out_of_range_returns_false():
    data = VectorLayerData()
    assert not data.remove(0)


def test_vector_layer_data_replace_swaps_in_place():
    data = VectorLayerData()
    s1 = VectorStroke(points=((0.0, 0.0),))
    s2 = VectorStroke(points=((10.0, 10.0),))
    data.add(s1)
    assert data.replace(0, s2)
    assert data.strokes == [s2]


def test_vector_layer_data_clear_empties_list():
    data = VectorLayerData()
    data.add(VectorStroke(points=((0.0, 0.0),)))
    data.clear()
    assert data.strokes == []


def test_vector_layer_data_render_caches_until_change():
    data = VectorLayerData()
    data.add(VectorStroke(points=((5.0, 5.0),), width=4.0))
    a = data.render((10, 10))
    b = data.render((10, 10))
    # Cached — same buffer.
    assert a is b
    data.add(VectorStroke(points=((9.0, 9.0),), width=4.0))
    c = data.render((10, 10))
    # Cache invalidated by the new stroke.
    assert c is not b


def test_vector_layer_data_render_invalidates_on_shape_change():
    data = VectorLayerData()
    data.add(VectorStroke(points=((5.0, 5.0),)))
    a = data.render((10, 10))
    b = data.render((20, 20))
    assert a is not b
    assert b.shape == (20, 20, 4)


# ---------------------------------------------------------------------------
# Document integration
# ---------------------------------------------------------------------------


def test_add_vector_layer_attaches_vector_data():
    doc = PaintDocument()
    doc.load_image(np.full((10, 10, 4), 0, dtype=np.uint8))
    layer = doc.add_vector_layer(name="Inks")
    assert layer.vector_data is not None
    assert layer.vector_data.strokes == []
    assert layer.image.shape == (10, 10, 4)


def test_add_vector_layer_requires_existing_document():
    doc = PaintDocument()
    with pytest.raises(RuntimeError, match="empty document"):
        doc.add_vector_layer()


def test_realise_vector_layer_paints_into_image():
    doc = PaintDocument()
    doc.load_image(np.zeros((20, 20, 4), dtype=np.uint8))
    layer = doc.add_vector_layer(name="Inks")
    layer.vector_data.add(
        VectorStroke(points=((10.0, 10.0),), width=4.0, color=(255, 0, 0, 255)),
    )
    assert realise_vector_layer(layer)
    # Image now has paint at the centre.
    assert layer.image[10, 10, 3] > 0


def test_realise_vector_layer_skips_raster_layers():
    doc = PaintDocument()
    doc.load_image(np.zeros((10, 10, 4), dtype=np.uint8))
    layer = doc.active_layer()
    assert layer.vector_data is None
    assert not realise_vector_layer(layer)


def test_realise_vector_layer_overwrites_old_pixels():
    """Removing a stroke must shrink the visible content — the
    rasteriser zeroes the cache before painting, so the previous
    stroke's pixels are gone."""
    doc = PaintDocument()
    doc.load_image(np.zeros((20, 20, 4), dtype=np.uint8))
    layer = doc.add_vector_layer(name="Inks")
    layer.vector_data.add(
        VectorStroke(points=((10.0, 10.0),), width=4.0, color=(255, 0, 0, 255)),
    )
    realise_vector_layer(layer)
    layer.vector_data.clear()
    realise_vector_layer(layer)
    # No strokes left → image is fully transparent again.
    assert (layer.image == 0).all()
