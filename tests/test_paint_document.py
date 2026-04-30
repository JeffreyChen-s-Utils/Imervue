"""Tests for the layer compositing pipeline + PaintDocument."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.compositing import (
    LAYER_BLEND_MODES,
    composite_layer_pair,
    composite_stack,
)
from Imervue.paint.document import (
    BACKGROUND_LAYER_NAME,
    Layer,
    PaintDocument,
)


def _layer(rgba: tuple[int, int, int, int], shape=(4, 4), **kwargs) -> Layer:
    arr = np.tile(np.array(rgba, dtype=np.uint8), shape + (1,))
    return Layer(name=kwargs.pop("name", "L"), image=arr, **kwargs)


# ---------------------------------------------------------------------------
# composite_layer_pair
# ---------------------------------------------------------------------------


def test_composite_pair_normal_full_alpha_replaces_below():
    below = np.full((4, 4, 4), 50, dtype=np.uint8)
    below[..., 3] = 255
    above = np.full((4, 4, 4), 200, dtype=np.uint8)
    above[..., 3] = 255
    out = composite_layer_pair(below, above)
    assert out[0, 0, 0] == 200


def test_composite_pair_zero_opacity_returns_below_copy():
    below = np.full((3, 3, 4), 50, dtype=np.uint8)
    above = np.full((3, 3, 4), 200, dtype=np.uint8)
    out = composite_layer_pair(below, above, opacity=0.0)
    np.testing.assert_array_equal(out, below)
    assert out is not below


def test_composite_pair_clamps_opacity_above_one():
    below = np.full((3, 3, 4), 50, dtype=np.uint8)
    above = np.full((3, 3, 4), 200, dtype=np.uint8)
    above[..., 3] = 255
    a = composite_layer_pair(below, above, opacity=1.0)
    b = composite_layer_pair(below, above, opacity=5.0)
    np.testing.assert_array_equal(a, b)


def test_composite_pair_rejects_unknown_blend_mode():
    a = np.zeros((2, 2, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        composite_layer_pair(a, a, blend_mode="vivid_glow")


def test_composite_pair_rejects_shape_mismatch():
    a = np.zeros((2, 2, 4), dtype=np.uint8)
    b = np.zeros((3, 3, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        composite_layer_pair(a, b)


def test_composite_pair_rejects_non_rgba_below(sample_rgb_array):
    other = np.zeros_like(sample_rgb_array)
    with pytest.raises(ValueError):
        composite_layer_pair(sample_rgb_array, other)


def test_composite_pair_mask_attenuates_above_layer():
    below = np.full((4, 4, 4), 50, dtype=np.uint8)
    below[..., 3] = 255
    above = np.full((4, 4, 4), 200, dtype=np.uint8)
    above[..., 3] = 255
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[1:3, 1:3] = 255
    out = composite_layer_pair(below, above, mask=mask)
    assert out[1, 1, 0] == 200
    assert out[0, 0, 0] == 50    # unmasked region keeps below


def test_composite_pair_rejects_mask_shape_mismatch():
    below = np.zeros((3, 3, 4), dtype=np.uint8)
    above = np.zeros((3, 3, 4), dtype=np.uint8)
    bad_mask = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        composite_layer_pair(below, above, mask=bad_mask)


def test_layer_blend_modes_listed():
    assert "normal" in LAYER_BLEND_MODES
    assert "soft_light" in LAYER_BLEND_MODES


# ---------------------------------------------------------------------------
# composite_stack
# ---------------------------------------------------------------------------


def test_composite_stack_empty_yields_transparent_canvas():
    out = composite_stack([], (4, 4))
    assert out.shape == (4, 4, 4)
    assert (out == 0).all()


def test_composite_stack_skips_invisible_layers():
    visible = _layer((10, 20, 30, 255), name="v")
    hidden = _layer((255, 0, 0, 255), name="h", visible=False)
    out = composite_stack([visible, hidden], (4, 4))
    assert out[0, 0, 0] == 10  # red layer was skipped


def test_composite_stack_rejects_layer_with_wrong_shape():
    big = _layer((0, 0, 0, 255), shape=(5, 5))
    with pytest.raises(ValueError):
        composite_stack([big], (4, 4))


def test_composite_stack_single_layer_fast_path_returns_image_buffer():
    """Hot path: a single fully-visible normal-blend layer is its own
    composite. Returning ``layer.image`` directly drops the per-stroke
    composite cost on a 1024² canvas from ~70 ms to ~0 — without that
    the brush feels visibly laggy."""
    layer = _layer((100, 150, 200, 255), name="solo")
    out = composite_stack([layer], (4, 4))
    assert out is layer.image


def test_composite_stack_skips_fast_path_for_partial_opacity():
    layer = _layer((100, 150, 200, 255), name="dim", opacity=0.5)
    out = composite_stack([layer], (4, 4))
    # Output is computed (not the same buffer) — opacity blending was
    # actually performed.
    assert out is not layer.image


def test_composite_stack_skips_fast_path_for_non_normal_blend():
    layer = _layer((100, 150, 200, 255), name="mul", blend_mode="multiply")
    out = composite_stack([layer], (4, 4))
    assert out is not layer.image


def test_composite_stack_skips_fast_path_for_invisible_layer():
    layer = _layer((100, 150, 200, 255), name="hidden", visible=False)
    out = composite_stack([layer], (4, 4))
    # Hidden layer must yield a transparent canvas, not the layer image.
    assert out is not layer.image
    assert (out == 0).all()


# ---------------------------------------------------------------------------
# Layer construction
# ---------------------------------------------------------------------------


def test_layer_rejects_non_rgba_image():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        Layer(name="bad", image=bad)


def test_layer_rejects_unknown_blend_mode():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        Layer(name="bad", image=arr, blend_mode="warp")


def test_layer_clamps_opacity():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    layer = Layer(name="x", image=arr, opacity=5.0)
    assert layer.opacity == 1.0


# ---------------------------------------------------------------------------
# PaintDocument
# ---------------------------------------------------------------------------


def test_document_starts_empty():
    doc = PaintDocument()
    assert doc.layer_count == 0
    assert doc.active_layer() is None
    assert doc.composite() is None


def test_document_load_image_creates_background_layer():
    doc = PaintDocument()
    arr = np.full((4, 4, 4), 255, dtype=np.uint8)
    doc.load_image(arr)
    assert doc.layer_count == 1
    assert doc.active_layer().name == BACKGROUND_LAYER_NAME
    assert doc.shape == (4, 4)


def test_document_load_image_rejects_non_rgba(sample_rgb_array):
    doc = PaintDocument()
    with pytest.raises(ValueError):
        doc.load_image(sample_rgb_array)


def test_document_add_layer_inserts_above_active():
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 100, dtype=np.uint8))
    new = doc.add_layer(name="Top")
    assert doc.layer_count == 2
    assert doc.active_layer() is new


def test_document_add_layer_on_empty_raises():
    doc = PaintDocument()
    with pytest.raises(RuntimeError):
        doc.add_layer()


def test_document_remove_does_not_drop_last_layer():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.remove_active_layer()
    assert doc.layer_count == 1   # Background preserved


def test_document_move_active_layer_up_swaps():
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 50, dtype=np.uint8))
    doc.add_layer(name="Top")  # active becomes index 1
    doc.set_active_layer(0)    # now Background is active
    doc.move_active_layer(up=True)
    # Background should now be at index 1.
    assert doc.layers()[1].name == BACKGROUND_LAYER_NAME


def test_document_move_active_layer_at_top_is_noop():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.add_layer()
    # Active is the top layer; moving up should be a no-op.
    initial = list(doc.layers())
    doc.move_active_layer(up=True)
    assert [a.name for a in doc.layers()] == [b.name for b in initial]


def test_document_duplicate_layer_inserts_copy():
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 200, dtype=np.uint8))
    doc.duplicate_active_layer()
    assert doc.layer_count == 2
    assert doc.layers()[1].name.endswith("copy")


def test_document_set_layer_attribute_updates_value():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_attribute(0, opacity=0.5)
    assert doc.layers()[0].opacity == 0.5


def test_document_set_layer_attribute_rejects_unknown_key():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    with pytest.raises(ValueError):
        doc.set_layer_attribute(0, unknown=42)


def test_document_set_layer_attribute_rejects_unknown_blend_mode():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    with pytest.raises(ValueError):
        doc.set_layer_attribute(0, blend_mode="warp")


def test_document_selection_persists_until_replaced():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    sel = np.zeros((4, 4), dtype=np.bool_)
    sel[1:3, 1:3] = True
    doc.set_selection(sel)
    assert doc.selection() is sel


def test_document_selection_shape_must_match():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    bad = np.zeros((3, 3), dtype=np.bool_)
    with pytest.raises(ValueError):
        doc.set_selection(bad)


def test_document_composite_caches_result():
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 100, dtype=np.uint8))
    a = doc.composite()
    b = doc.composite()
    assert a is b   # cached


def test_document_invalidate_composite_reflects_layer_mutation():
    """After ``invalidate_composite`` the next ``composite`` call must
    reflect the current layer state. For multi-layer / non-trivial
    cases that means a fresh allocation; for the single-layer fast
    path, ``composite`` returns ``layer.image`` directly so any in-
    place mutation is already visible — both behaviours satisfy "the
    composite is up to date after invalidation"."""
    doc = PaintDocument()
    arr = np.full((4, 4, 4), 100, dtype=np.uint8)
    doc.load_image(arr)
    doc.composite()  # populate the cache
    # Mutate the layer in place, then invalidate.
    doc.active_layer().image[0, 0] = (200, 50, 25, 255)
    doc.invalidate_composite()
    refreshed = doc.composite()
    assert tuple(refreshed[0, 0]) == (200, 50, 25, 255)


def test_document_listeners_receive_change_notifications():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    received: list[bool] = []
    doc.listen(lambda: received.append(True))
    doc.add_layer()
    assert len(received) >= 1


def test_document_active_layer_index_clamped_after_remove():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.add_layer()
    doc.remove_active_layer()
    assert doc.active_layer_index() == 0
