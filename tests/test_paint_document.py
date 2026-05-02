"""Tests for the layer compositing pipeline + PaintDocument."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.compositing import (
    LAYER_BLEND_MODES,
    composite_layer_pair,
    composite_region,
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
# composite_region — partial recompose used by mark_composite_dirty
# ---------------------------------------------------------------------------


def test_composite_region_matches_full_composite_inside_rect():
    """Region recompose must equal the corresponding slice of the full
    composite for plain raster layers — otherwise brush dabs would
    leave the cached frame in a mathematically different state from
    what a full rebuild would produce."""
    bottom = _layer((40, 50, 60, 255), shape=(8, 8), name="b")
    top = _layer((10, 200, 100, 255), shape=(8, 8), name="t",
                 opacity=0.5, blend_mode="screen")
    full = composite_stack([bottom, top], (8, 8))
    rect = (2, 3, 4, 3)
    partial = composite_region([bottom, top], (8, 8), rect)
    assert partial is not None
    np.testing.assert_array_equal(
        partial,
        full[rect[1]:rect[1] + rect[3], rect[0]:rect[0] + rect[2]],
    )


def test_composite_region_returns_none_for_layer_with_effects():
    """Layer effects (drop shadow / glow / stroke) leak past the layer
    bounds — partial recompose can't see that context, so return None
    and let the caller fall back to a full composite."""
    layer = _layer((100, 100, 100, 255), shape=(8, 8), name="fx")
    layer.effects = ({"kind": "drop_shadow"},)
    out = composite_region([layer], (8, 8), (1, 1, 4, 4))
    assert out is None


def test_mark_composite_dirty_patches_only_the_rect():
    """The cache returned after a brush dab must equal a full rebuild
    when the only change is inside the marked rect."""
    doc = PaintDocument()
    doc.load_image(np.full((6, 8, 4), 0, dtype=np.uint8))
    top = doc.add_layer(name="top")
    top.image[...] = (200, 100, 50, 255)
    first = doc.composite()
    assert first is not None
    cached_id = id(first)
    top.image[2:4, 3:6] = (5, 5, 5, 255)
    doc.mark_composite_dirty((3, 2, 3, 2))
    patched = doc.composite()
    # Cache buffer is reused — patching the dirty rect should not
    # reallocate the array.
    assert id(patched) == cached_id
    expected = composite_stack(doc.layers(), doc.shape, groups=doc._groups)  # noqa: SLF001
    np.testing.assert_array_equal(patched, expected)


def test_mark_composite_dirty_clipped_off_canvas_is_dropped():
    """Off-canvas rects must not raise or blow away the cache —
    brush dabs at the edge can produce damage that overlaps the
    image boundary and the canvas relies on graceful clipping."""
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 0, dtype=np.uint8))
    doc.composite()  # prime cache
    cache_before = doc._composite_cache  # noqa: SLF001
    doc.mark_composite_dirty((-10, -10, 5, 5))
    # Fully off-canvas — cache stays untouched.
    assert doc._composite_cache is cache_before  # noqa: SLF001
    assert doc._composite_dirty_rect is None  # noqa: SLF001


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


# ---------------------------------------------------------------------------
# Layer colour labels + search
# ---------------------------------------------------------------------------


def test_layer_color_label_defaults_to_none():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.active_layer().color_label is None


def test_layer_rejects_unknown_color_label():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="unknown color_label"):
        Layer(name="bad", image=arr, color_label="rainbow")


def test_set_layer_color_label_sets_and_returns_true():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.set_layer_color_label(label="red") is True
    assert doc.active_layer().color_label == "red"


def test_set_layer_color_label_idempotent():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_color_label(label="red")
    assert doc.set_layer_color_label(label="red") is False


def test_set_layer_color_label_clears_with_none():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_color_label(label="red")
    assert doc.set_layer_color_label(label=None) is True
    assert doc.active_layer().color_label is None


def test_set_layer_color_label_rejects_unknown():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match="unknown color_label"):
        doc.set_layer_color_label(label="ultraviolet")


def test_find_layers_empty_query_returns_all_indices():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.add_layer(name="Inks")
    doc.add_layer(name="Flats")
    assert doc.find_layers("") == [0, 1, 2]


def test_find_layers_case_insensitive_substring():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.add_layer(name="Inks")
    doc.add_layer(name="Flats")
    assert doc.find_layers("INK") == [1]


def test_find_layers_and_combines_tokens():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.add_layer(name="Cool Ambient Glow")
    doc.add_layer(name="Warm Highlights")
    # Both tokens "cool" + "glow" must match; only the Ambient Glow
    # layer matches both.
    assert doc.find_layers("cool glow") == [1]


def test_find_layers_no_match_returns_empty():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.find_layers("nonexistent") == []


# ---------------------------------------------------------------------------
# Reference layer (bucket sampling)
# ---------------------------------------------------------------------------


def _doc_with_layers(n: int = 3) -> PaintDocument:
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    for _ in range(n - 1):
        doc.add_layer()
    return doc


def test_reference_layer_index_defaults_to_none():
    doc = _doc_with_layers(2)
    assert doc.reference_layer_index() is None
    assert doc.reference_layer_image() is None


def test_set_reference_layer_index_returns_true_on_change():
    doc = _doc_with_layers(2)
    assert doc.set_reference_layer_index(0) is True
    assert doc.reference_layer_index() == 0


def test_set_reference_layer_index_idempotent_returns_false():
    doc = _doc_with_layers(2)
    doc.set_reference_layer_index(0)
    assert doc.set_reference_layer_index(0) is False


def test_set_reference_layer_index_clear_with_none():
    doc = _doc_with_layers(2)
    doc.set_reference_layer_index(0)
    assert doc.set_reference_layer_index(None) is True
    assert doc.reference_layer_index() is None


def test_set_reference_layer_index_rejects_out_of_range():
    doc = _doc_with_layers(2)
    with pytest.raises(IndexError):
        doc.set_reference_layer_index(99)


def test_reference_layer_image_returns_the_layer_buffer():
    doc = _doc_with_layers(2)
    doc.layer_at(0).image[:] = (10, 20, 30, 255)
    doc.set_reference_layer_index(0)
    img = doc.reference_layer_image()
    assert img is not None
    assert tuple(img[0, 0]) == (10, 20, 30, 255)


def test_reference_layer_image_returns_none_when_layer_hidden():
    doc = _doc_with_layers(2)
    doc.set_reference_layer_index(0)
    doc.set_layer_attribute(0, visible=False)
    assert doc.reference_layer_image() is None


def test_reference_index_shifts_when_new_layer_inserted_below():
    """add_layer above an active that sits below the reference must
    bump the reference index up so it still points at the same layer.
    """
    doc = _doc_with_layers(2)
    doc.set_active_layer(0)
    doc.set_reference_layer_index(1)
    doc.add_layer()  # inserts at index 1, pushing old index-1 to 2
    assert doc.reference_layer_index() == 2


def test_reference_index_drops_when_reference_layer_removed():
    doc = _doc_with_layers(3)
    doc.set_active_layer(1)
    doc.set_reference_layer_index(1)
    doc.remove_active_layer()
    assert doc.reference_layer_index() is None


def test_reference_index_shifts_down_when_lower_layer_removed():
    doc = _doc_with_layers(3)
    doc.set_reference_layer_index(2)
    doc.set_active_layer(0)
    doc.remove_active_layer()
    assert doc.reference_layer_index() == 1


def test_reference_index_swaps_with_move_active_layer():
    doc = _doc_with_layers(3)
    doc.set_reference_layer_index(2)
    doc.set_active_layer(2)
    doc.move_active_layer(up=False)
    assert doc.reference_layer_index() == 1


def test_reference_index_cleared_by_load_image():
    doc = _doc_with_layers(2)
    doc.set_reference_layer_index(0)
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.reference_layer_index() is None


def test_reference_index_cleared_by_flatten():
    doc = _doc_with_layers(3)
    doc.set_reference_layer_index(1)
    doc.flatten()
    assert doc.reference_layer_index() is None


def test_replace_state_accepts_reference_layer_index():
    doc = PaintDocument()
    h, w = 4, 4
    layers = [
        Layer(name="A", image=np.zeros((h, w, 4), dtype=np.uint8)),
        Layer(name="B", image=np.zeros((h, w, 4), dtype=np.uint8)),
    ]
    doc.replace_state(layers=layers, reference_layer_index=1)
    assert doc.reference_layer_index() == 1


def test_replace_state_clamps_invalid_reference_to_none():
    doc = PaintDocument()
    h, w = 4, 4
    layers = [Layer(name="A", image=np.zeros((h, w, 4), dtype=np.uint8))]
    doc.replace_state(layers=layers, reference_layer_index=99)
    assert doc.reference_layer_index() is None


# ---------------------------------------------------------------------------
# Per-layer tone (halftone-render hint)
# ---------------------------------------------------------------------------


def test_layer_defaults_tone_to_none():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.active_layer().tone is None


def test_set_layer_tone_assigns_settings():
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    tone = ToneSettings(lpi=80)
    assert doc.set_layer_tone(tone=tone) is True
    assert doc.active_layer().tone == tone


def test_set_layer_tone_idempotent_returns_false():
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_tone(tone=ToneSettings())
    assert doc.set_layer_tone(tone=ToneSettings()) is False


def test_set_layer_tone_clear_with_none():
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_tone(tone=ToneSettings())
    assert doc.set_layer_tone(tone=None) is True
    assert doc.active_layer().tone is None


def test_duplicate_active_layer_carries_tone():
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_tone(tone=ToneSettings(lpi=70))
    doc.duplicate_active_layer()
    duplicated = doc.active_layer()
    assert duplicated.tone is not None
    assert duplicated.tone.lpi == 70


def test_compositor_renders_tone_layer():
    """A tone layer's grey content should composite as a sparse dot
    pattern instead of the original soft fill."""
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    grey = np.full((32, 32, 4), 128, dtype=np.uint8)
    grey[..., 3] = 255
    doc.load_image(grey)
    plain = doc.composite()
    assert plain is not None
    plain_unique = len(np.unique(plain[..., 3]))
    doc.set_layer_tone(tone=ToneSettings(lpi=60))
    toned = doc.composite()
    assert toned is not None
    toned_unique = len(np.unique(toned[..., 3]))
    # Plain raster: composite alpha is uniform (a single value or a
    # very small set). Toned: alpha is bimodal between dot interior /
    # exterior, producing more distinct alpha values.
    assert toned_unique > plain_unique


def test_compositor_skips_tone_when_unset():
    from Imervue.paint.halftone import ToneSettings
    doc = PaintDocument()
    grey = np.full((32, 32, 4), 100, dtype=np.uint8)
    grey[..., 3] = 255
    doc.load_image(grey)
    base = doc.composite()
    doc.set_layer_tone(tone=ToneSettings())
    doc.set_layer_tone(tone=None)
    after_clear = doc.composite()
    np.testing.assert_array_equal(base, after_clear)


# ---------------------------------------------------------------------------
# Per-layer binary (1-bit ink hint)
# ---------------------------------------------------------------------------


def test_layer_defaults_binary_to_none():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.active_layer().binary is None


def test_set_layer_binary_assigns_settings():
    from Imervue.paint.binary_layer import BinarySettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    settings = BinarySettings(threshold=200)
    assert doc.set_layer_binary(binary=settings) is True
    assert doc.active_layer().binary == settings


def test_set_layer_binary_idempotent_returns_false():
    from Imervue.paint.binary_layer import BinarySettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_binary(binary=BinarySettings())
    assert doc.set_layer_binary(binary=BinarySettings()) is False


def test_set_layer_binary_clear_with_none():
    from Imervue.paint.binary_layer import BinarySettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_binary(binary=BinarySettings())
    assert doc.set_layer_binary(binary=None) is True
    assert doc.active_layer().binary is None


def test_duplicate_active_layer_carries_binary():
    from Imervue.paint.binary_layer import BinarySettings
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    doc.set_layer_binary(binary=BinarySettings(threshold=180))
    doc.duplicate_active_layer()
    duplicated = doc.active_layer()
    assert duplicated.binary is not None
    assert duplicated.binary.threshold == 180


def test_compositor_renders_binary_layer():
    """Soft greys composite as bimodal ink-or-transparent under
    a binary hint."""
    from Imervue.paint.binary_layer import BinarySettings
    doc = PaintDocument()
    soft = np.zeros((16, 16, 4), dtype=np.uint8)
    soft[..., 3] = np.arange(0, 256, 16, dtype=np.uint8)[:, None]
    doc.load_image(soft)
    doc.set_layer_binary(binary=BinarySettings(threshold=128))
    out = doc.composite()
    assert out is not None
    # Every pixel's alpha is either 0 or 255 — no intermediate values.
    unique_alphas = set(np.unique(out[..., 3]).tolist())
    assert unique_alphas.issubset({0, 255})


# ---------------------------------------------------------------------------
# Divide layer (auto colour separation)
# ---------------------------------------------------------------------------


def test_divide_active_layer_returns_zero_for_empty_layer():
    doc = PaintDocument()
    doc.load_image(np.zeros((4, 4, 4), dtype=np.uint8))
    assert doc.divide_active_layer() == 0
    # Stack unchanged.
    assert doc.layer_count == 1


def test_divide_active_layer_splits_two_colours():
    doc = PaintDocument()
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :2, :3] = (255, 0, 0)
    img[:, 2:, :3] = (0, 0, 255)
    doc.load_image(img)
    inserted = doc.divide_active_layer()
    assert inserted == 2
    assert doc.layer_count == 2


def test_divide_active_layer_renders_per_colour_alpha():
    doc = PaintDocument()
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :2, :3] = (255, 0, 0)
    img[:, 2:, :3] = (0, 0, 255)
    doc.load_image(img)
    doc.divide_active_layer()
    layers = doc.layers()
    # Each output layer has alpha only inside its mask, so the union
    # of their alpha matches the original opaque region.
    union_alpha = np.zeros((4, 4), dtype=np.uint8)
    for layer in layers:
        union_alpha = np.maximum(union_alpha, layer.image[..., 3])
    assert (union_alpha == 255).all()


def test_divide_active_layer_clears_reference_pointing_at_source():
    doc = PaintDocument()
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., 3] = 255
    img[:, :2, :3] = (10, 200, 30)
    img[:, 2:, :3] = (200, 30, 10)
    doc.load_image(img)
    doc.set_reference_layer_index(0)
    doc.divide_active_layer()
    assert doc.reference_layer_index() is None

