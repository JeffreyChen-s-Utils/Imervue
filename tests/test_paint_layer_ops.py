"""Tests for layer composition ops + the PaintDocument hooks."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import Layer, PaintDocument
from Imervue.paint.layer_ops import (
    composite_visible_layers,
    flatten_layers,
    merge_layer_pair,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _solid_layer(name: str, color: tuple[int, int, int, int],
                 shape: tuple[int, int] = (8, 8), **kwargs) -> Layer:
    h, w = shape
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = color[0]
    img[..., 1] = color[1]
    img[..., 2] = color[2]
    img[..., 3] = color[3]
    return Layer(name=name, image=img, **kwargs)


@pytest.fixture
def document_with_two_layers():
    doc = PaintDocument()
    base = np.full((8, 8, 4), 255, dtype=np.uint8)
    base[..., :3] = (200, 100, 50)
    doc.load_image(base)
    above = doc.add_layer(name="Above")
    above.image[..., :3] = (50, 100, 200)
    above.image[..., 3] = 255
    doc.invalidate_composite()
    return doc


# ---------------------------------------------------------------------------
# merge_layer_pair
# ---------------------------------------------------------------------------


def test_merge_layer_pair_returns_new_layer():
    below = _solid_layer("Below", (200, 0, 0, 255))
    above = _solid_layer("Above", (0, 0, 200, 255))
    merged = merge_layer_pair(below, above)
    assert merged is not below
    assert merged is not above


def test_merge_layer_pair_preserves_below_name_and_blend():
    below = _solid_layer("Below", (200, 0, 0, 255), opacity=0.5,
                         blend_mode="multiply")
    above = _solid_layer("Above", (0, 0, 200, 255))
    merged = merge_layer_pair(below, above)
    assert merged.name == "Below"
    assert merged.opacity == pytest.approx(0.5)
    assert merged.blend_mode == "multiply"


def test_merge_layer_pair_drops_above_mask():
    below = _solid_layer("Below", (200, 0, 0, 255))
    above = _solid_layer("Above", (0, 0, 200, 255))
    above.mask = np.full((8, 8), 128, dtype=np.uint8)
    merged = merge_layer_pair(below, above)
    assert merged.mask is None


def test_merge_layer_pair_bakes_above_pixels():
    """A fully-opaque above should overwrite the below RGB."""
    below = _solid_layer("Below", (200, 0, 0, 255))
    above = _solid_layer("Above", (0, 0, 200, 255))
    merged = merge_layer_pair(below, above)
    assert merged.image[0, 0, 2] == 200
    assert merged.image[0, 0, 0] == 0


def test_merge_layer_pair_does_not_mutate_inputs():
    below = _solid_layer("Below", (200, 0, 0, 255))
    above = _solid_layer("Above", (0, 0, 200, 255))
    below_snapshot = below.image.copy()
    above_snapshot = above.image.copy()
    merge_layer_pair(below, above)
    np.testing.assert_array_equal(below.image, below_snapshot)
    np.testing.assert_array_equal(above.image, above_snapshot)


def test_merge_layer_pair_rejects_shape_mismatch():
    below = _solid_layer("Below", (200, 0, 0, 255), shape=(8, 8))
    above = _solid_layer("Above", (0, 0, 200, 255), shape=(4, 4))
    with pytest.raises(ValueError, match="equal-shape"):
        merge_layer_pair(below, above)


# ---------------------------------------------------------------------------
# composite_visible_layers
# ---------------------------------------------------------------------------


def test_composite_visible_returns_none_when_all_hidden():
    layers = [_solid_layer("A", (200, 0, 0, 255), visible=False)]
    out = composite_visible_layers(layers, (8, 8))
    assert out is None


def test_composite_visible_returns_none_when_all_zero_opacity():
    layers = [_solid_layer("A", (200, 0, 0, 255), opacity=0.0)]
    out = composite_visible_layers(layers, (8, 8))
    assert out is None


def test_composite_visible_returns_normal_blend_layer():
    a = _solid_layer("A", (200, 0, 0, 255))
    b = _solid_layer("B", (0, 0, 200, 255), blend_mode="multiply")
    merged = composite_visible_layers([a, b], (8, 8))
    assert merged is not None
    assert merged.blend_mode == "normal"
    assert merged.opacity == pytest.approx(1.0)


def test_composite_visible_uses_lowest_visible_name():
    a = _solid_layer("Below", (200, 0, 0, 255))
    b = _solid_layer("Above", (0, 0, 200, 255))
    merged = composite_visible_layers([a, b], (8, 8))
    assert merged is not None
    assert merged.name == "Below"


def test_composite_visible_skips_hidden_layer():
    visible = _solid_layer("V", (200, 0, 0, 255))
    hidden = _solid_layer("H", (0, 0, 200, 255), visible=False)
    merged = composite_visible_layers([visible, hidden], (8, 8))
    # Hidden contribution is dropped — output should match the
    # visible layer's RGB (composited over a transparent base).
    assert merged is not None
    assert merged.image[0, 0, 0] == 200
    assert merged.image[0, 0, 2] == 0


def test_composite_visible_rejects_shape_mismatch():
    bad = _solid_layer("Bad", (200, 0, 0, 255), shape=(4, 4))
    with pytest.raises(ValueError, match="does not match"):
        composite_visible_layers([bad], (8, 8))


# ---------------------------------------------------------------------------
# flatten_layers
# ---------------------------------------------------------------------------


def test_flatten_empty_returns_transparent_background():
    out = flatten_layers([], (8, 8))
    assert out.name == "Background"
    assert out.image.shape == (8, 8, 4)
    assert out.image[..., 3].sum() == 0


def test_flatten_returns_named_background_layer():
    a = _solid_layer("A", (200, 0, 0, 255))
    out = flatten_layers([a], (8, 8))
    assert out.name == "Background"


def test_flatten_drops_hidden_layers():
    visible = _solid_layer("V", (200, 0, 0, 255))
    hidden = _solid_layer("H", (0, 0, 200, 255), visible=False)
    out = flatten_layers([visible, hidden], (8, 8))
    # Only the visible layer's RGB shows up.
    assert out.image[0, 0, 0] == 200


# ---------------------------------------------------------------------------
# PaintDocument.merge_down
# ---------------------------------------------------------------------------


def test_document_merge_down_collapses_two_layers(document_with_two_layers):
    doc = document_with_two_layers
    assert doc.layer_count == 2
    assert doc.merge_down() is True
    assert doc.layer_count == 1


def test_document_merge_down_active_becomes_lower_index(document_with_two_layers):
    doc = document_with_two_layers
    doc.merge_down()
    assert doc.active_layer_index() == 0


def test_document_merge_down_at_bottom_layer_returns_false():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    assert doc.active_layer_index() == 0
    assert doc.merge_down() is False
    assert doc.layer_count == 1


def test_document_merge_down_notifies_listeners(document_with_two_layers):
    doc = document_with_two_layers
    calls = []
    doc.listen(lambda: calls.append(1))
    doc.merge_down()
    assert calls   # at least one notification fired


# ---------------------------------------------------------------------------
# PaintDocument.merge_visible
# ---------------------------------------------------------------------------


def test_document_merge_visible_keeps_hidden_layers():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    above = doc.add_layer(name="Above")
    above.image[..., 3] = 255
    hidden = doc.add_layer(name="Hidden")
    hidden.image[..., 3] = 255
    hidden.visible = False
    doc.invalidate_composite()

    assert doc.layer_count == 3
    assert doc.merge_visible() is True
    # Two visible merged → 1; hidden survives → final count = 2.
    assert doc.layer_count == 2
    # The kept layer is the hidden one.
    names = [layer.name for layer in doc.layers()]
    assert "Hidden" in names


def test_document_merge_visible_with_single_visible_is_noop():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    hidden = doc.add_layer(name="Hidden", on_top_of_active=True)
    hidden.visible = False
    assert doc.merge_visible() is False


# ---------------------------------------------------------------------------
# PaintDocument.flatten
# ---------------------------------------------------------------------------


def test_document_flatten_collapses_to_one_background_layer():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    doc.add_layer(name="Above")
    doc.add_layer(name="Higher")
    assert doc.flatten() is True
    assert doc.layer_count == 1
    assert doc.layers()[0].name == "Background"


def test_document_flatten_drops_hidden_layers_too():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    hidden = doc.add_layer(name="Hidden")
    hidden.visible = False
    assert doc.flatten() is True
    assert doc.layer_count == 1


def test_document_flatten_active_pointer_resets_to_zero():
    doc = PaintDocument()
    doc.load_image(np.full((8, 8, 4), 255, dtype=np.uint8))
    doc.add_layer(name="A")
    doc.add_layer(name="B")
    doc.flatten()
    assert doc.active_layer_index() == 0


def test_document_flatten_empty_doc_returns_false():
    doc = PaintDocument()
    assert doc.flatten() is False
