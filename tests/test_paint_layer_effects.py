"""Tests for layer effects (drop shadow / outer glow / stroke)."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.layer_effects import (
    EFFECT_KINDS,
    LayerEffect,
    apply_effects,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _layer_with_centred_square(h=20, w=20, color=(200, 100, 50)):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[5:15, 5:15, 0] = color[0]
    img[5:15, 5:15, 1] = color[1]
    img[5:15, 5:15, 2] = color[2]
    img[5:15, 5:15, 3] = 255
    return img


# ---------------------------------------------------------------------------
# LayerEffect dataclass
# ---------------------------------------------------------------------------


def test_effect_kinds_set():
    assert set(EFFECT_KINDS) == {"drop_shadow", "outer_glow", "stroke"}


def test_layer_effect_construction():
    e = LayerEffect(kind="drop_shadow", params={"radius": 4})
    assert e.kind == "drop_shadow"
    assert e.params["radius"] == 4


def test_layer_effect_is_frozen():
    e = LayerEffect(kind="drop_shadow")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.kind = "stroke"  # type: ignore[misc]


def test_layer_effect_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown layer-effect"):
        LayerEffect(kind="rainbow")


def test_layer_effect_rejects_non_dict_params():
    with pytest.raises(ValueError, match="dict"):
        LayerEffect(kind="drop_shadow", params="bad")  # type: ignore[arg-type]


def test_layer_effect_round_trip_via_dict():
    e = LayerEffect(
        kind="stroke", params={"width": 5, "color": [255, 0, 0, 255]},
    )
    rebuilt = LayerEffect.from_dict(e.to_dict())
    assert rebuilt.kind == "stroke"
    assert rebuilt.params["width"] == 5
    assert rebuilt.params["color"] == [255, 0, 0, 255]


def test_layer_effect_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        LayerEffect.from_dict("garbage")  # type: ignore[arg-type]  # NOSONAR — intentional negative-path test


def test_layer_effect_from_dict_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown"):
        LayerEffect.from_dict({"kind": "rainbow"})


def test_layer_effect_from_dict_supplies_defaults_for_missing_params():
    rebuilt = LayerEffect.from_dict({"kind": "drop_shadow", "params": {}})
    # Default radius is non-zero so the merge works.
    assert rebuilt.params["radius"] >= 0


# ---------------------------------------------------------------------------
# apply_effects
# ---------------------------------------------------------------------------


def test_apply_effects_no_effects_returns_input():
    img = _layer_with_centred_square()
    out = apply_effects(img, ())
    np.testing.assert_array_equal(out, img)


def test_apply_effects_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        apply_effects(rgb, (LayerEffect(kind="drop_shadow"),))


def test_apply_effects_first_occurrence_wins():
    """Two drop shadows in the list — only the first applies."""
    img = _layer_with_centred_square()
    out_one = apply_effects(
        img,
        (LayerEffect(kind="drop_shadow", params={"offset_x": 3, "offset_y": 3, "radius": 0}),),
    )
    out_two = apply_effects(
        img,
        (
            LayerEffect(kind="drop_shadow", params={"offset_x": 3, "offset_y": 3, "radius": 0}),
            LayerEffect(kind="drop_shadow", params={"offset_x": 10, "offset_y": 10, "radius": 0}),
        ),
    )
    np.testing.assert_array_equal(out_one, out_two)


# ---------------------------------------------------------------------------
# Drop shadow
# ---------------------------------------------------------------------------


def test_drop_shadow_appears_at_offset_position():
    """A 5x5 right/down offset shadow should darken the canvas where the
    original pixels weren't."""
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="drop_shadow",
            params={"offset_x": 5, "offset_y": 5, "radius": 0,
                    "opacity": 1.0, "color": [0, 0, 0, 255]},
        ),),
    )
    # Pixel just outside the original square but inside the shadow band.
    assert out[19, 19, 3] > 0
    assert out[19, 19, 0] < 100   # dark shadow colour


def test_drop_shadow_does_not_overwrite_layer_pixels():
    img = _layer_with_centred_square(color=(200, 100, 50))
    out = apply_effects(
        img,
        (LayerEffect(
            kind="drop_shadow",
            params={"offset_x": 0, "offset_y": 0, "radius": 6,
                    "opacity": 1.0, "color": [0, 0, 0, 255]},
        ),),
    )
    # The layer's interior keeps its colour — shadow renders BEHIND.
    assert out[10, 10, 0] == 200
    assert out[10, 10, 1] == 100


def test_drop_shadow_zero_opacity_yields_input():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="drop_shadow",
            params={"offset_x": 5, "offset_y": 5, "opacity": 0.0},
        ),),
    )
    np.testing.assert_array_equal(out, img)


# ---------------------------------------------------------------------------
# Outer glow
# ---------------------------------------------------------------------------


def test_outer_glow_paints_around_layer():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="outer_glow",
            params={"radius": 4, "opacity": 1.0,
                    "color": [255, 200, 0, 255], "intensity": 2.0},
        ),),
    )
    # Just outside the original square — glow contribution.
    assert out[3, 10, 0] > 200
    assert out[3, 10, 1] > 100


def test_outer_glow_zero_radius_still_runs_safely():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="outer_glow",
            params={"radius": 0, "opacity": 0.5,
                    "color": [255, 200, 0, 255]},
        ),),
    )
    # Shape is preserved; doesn't raise.
    assert out.shape == img.shape


# ---------------------------------------------------------------------------
# Stroke
# ---------------------------------------------------------------------------


def test_stroke_outside_paints_pixels_around_layer():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="stroke",
            params={"width": 2, "placement": "outside",
                    "color": [255, 0, 0, 255], "opacity": 1.0},
        ),),
    )
    # Pixel one row above the original square should now be red.
    assert tuple(out[4, 10, :3]) == (255, 0, 0)


def test_stroke_inside_paints_pixels_inside_layer_silhouette():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="stroke",
            params={"width": 2, "placement": "inside",
                    "color": [255, 0, 0, 255], "opacity": 1.0},
        ),),
    )
    # The interior 2-px ring is repainted — pixel at (5, 5) (the corner)
    # should be red instead of the layer's original colour.
    assert out[5, 5, 0] == 255


def test_stroke_zero_width_is_noop():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(kind="stroke", params={"width": 0}),),
    )
    np.testing.assert_array_equal(out, img)


def test_stroke_unknown_placement_falls_back_to_outside():
    img = _layer_with_centred_square()
    out = apply_effects(
        img,
        (LayerEffect(
            kind="stroke",
            params={"width": 2, "placement": "spiral",
                    "color": [255, 0, 0, 255]},
        ),),
    )
    # Outside-stroke behaviour: pixel above the original silhouette is
    # painted red.
    assert tuple(out[4, 10, :3]) == (255, 0, 0)


# ---------------------------------------------------------------------------
# PaintDocument integration
# ---------------------------------------------------------------------------


def test_set_layer_effects_replaces_tuple():
    doc = PaintDocument()
    doc.load_image(_layer_with_centred_square())
    effects = (LayerEffect(kind="drop_shadow"),)
    assert doc.set_layer_effects(effects=effects) is True
    assert doc.active_layer().effects == effects


def test_set_layer_effects_idempotent_returns_false():
    doc = PaintDocument()
    doc.load_image(_layer_with_centred_square())
    effects = (LayerEffect(kind="drop_shadow"),)
    doc.set_layer_effects(effects=effects)
    assert doc.set_layer_effects(effects=effects) is False


def test_composite_renders_layer_effects():
    doc = PaintDocument()
    doc.load_image(_layer_with_centred_square())
    doc.set_layer_effects(
        effects=(LayerEffect(
            kind="stroke",
            params={"width": 1, "placement": "outside",
                    "color": [255, 0, 0, 255]},
        ),),
    )
    out = doc.composite()
    # Pixel one row above the original square should be red after
    # compositing applies the stroke effect.
    assert out is not None
    assert out[4, 10, 0] == 255


def test_layer_effects_persist_via_document_io(tmp_path):
    from Imervue.paint.document_io import load_document, save_document
    doc = PaintDocument()
    doc.load_image(_layer_with_centred_square())
    doc.set_layer_effects(
        effects=(LayerEffect(kind="drop_shadow", params={"radius": 5}),),
    )
    path = tmp_path / "fx.imervue"
    save_document(doc, path)
    loaded = load_document(path)
    effects = loaded.layers()[0].effects
    assert len(effects) == 1
    assert effects[0].kind == "drop_shadow"
    assert effects[0].params["radius"] == 5
