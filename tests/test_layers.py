"""Tests for the layer compositing module + dialog helpers."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.layers import (
    BLEND_MODES,
    MAX_LAYERS,
    Layer,
    apply_layers,
    layers_from_dict_list,
    layers_to_dict_list,
)


# ---------------------------------------------------------------------------
# Layer dataclass / serialisation
# ---------------------------------------------------------------------------


def test_layer_defaults():
    layer = Layer()
    assert layer.kind == "text"
    assert layer.enabled is True
    assert layer.opacity == 1.0
    assert layer.blend_mode == "normal"
    assert layer.params == {}


def test_layer_round_trip_serialisation():
    layer = Layer(
        kind="image",
        enabled=False,
        opacity=0.7,
        blend_mode="multiply",
        params={"path": "/var/data/x.png"},
    )
    restored = Layer.from_dict(layer.to_dict())
    assert restored.kind == "image"
    assert restored.enabled is False
    assert restored.opacity == pytest.approx(0.7)
    assert restored.blend_mode == "multiply"
    assert restored.params == {"path": "/var/data/x.png"}


def test_layer_from_dict_normalises_unknown_kind():
    restored = Layer.from_dict({"kind": "garbage"})
    assert restored.kind == "text"  # falls back to default


def test_layer_from_dict_normalises_unknown_blend_mode():
    restored = Layer.from_dict({"kind": "text", "blend_mode": "bogus"})
    assert restored.blend_mode == "normal"


def test_layer_from_dict_clamps_opacity():
    assert Layer.from_dict({"opacity": 3.0}).opacity == 1.0
    assert Layer.from_dict({"opacity": -2.0}).opacity == 0.0


def test_layers_from_dict_list_skips_garbage_entries():
    raw = [{"kind": "text"}, "not-a-dict", {"kind": "image"}]
    layers = layers_from_dict_list(raw)
    assert len(layers) == 2
    assert [lyr.kind for lyr in layers] == ["text", "image"]


def test_layers_from_dict_list_caps_at_max():
    raw = [{"kind": "text"}] * (MAX_LAYERS + 5)
    assert len(layers_from_dict_list(raw)) == MAX_LAYERS


def test_layers_to_dict_list_round_trip():
    original = [
        Layer(kind="text", params={"text": "hi"}),
        Layer(kind="lut", params={"path": "/var/data/x.cube"}),
    ]
    restored = layers_from_dict_list(layers_to_dict_list(original))
    assert restored[0].kind == "text"
    assert restored[0].params["text"] == "hi"
    assert restored[1].kind == "lut"
    assert restored[1].params["path"] == "/var/data/x.cube"


# ---------------------------------------------------------------------------
# apply_layers — compositing pipeline
# ---------------------------------------------------------------------------


def _solid_rgba(h: int, w: int, rgb: tuple[int, int, int]) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = 255
    return arr


def test_apply_layers_no_layers_is_identity():
    base = _solid_rgba(10, 10, (100, 50, 200))
    out = apply_layers(base, [])
    assert np.array_equal(out, base)


def test_apply_layers_disabled_is_identity():
    base = _solid_rgba(10, 10, (100, 50, 200))
    layer = Layer(kind="text", enabled=False, params={"text": "hello"})
    out = apply_layers(base, [layer])
    assert np.array_equal(out, base)


def test_apply_layers_zero_opacity_is_identity():
    base = _solid_rgba(10, 10, (100, 50, 200))
    layer = Layer(kind="text", opacity=0.0, params={"text": "hello"})
    out = apply_layers(base, [layer])
    assert np.array_equal(out, base)


def test_apply_layers_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_layers(rgb, [Layer()])


def test_apply_layers_rejects_wrong_dtype():
    base = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        apply_layers(base, [Layer()])


def test_apply_layers_text_layer_modifies_pixels():
    base = _solid_rgba(64, 64, (50, 50, 50))
    layer = Layer(
        kind="text",
        enabled=True,
        opacity=1.0,
        blend_mode="normal",
        params={"text": "X", "corner": "center", "font_fraction": 0.3,
                "color": [255, 0, 0], "shadow": False},
    )
    out = apply_layers(base, [layer])
    assert not np.array_equal(out, base)


def test_apply_layers_skips_text_layer_with_empty_string():
    base = _solid_rgba(32, 32, (10, 20, 30))
    layer = Layer(kind="text", params={"text": "   "})
    out = apply_layers(base, [layer])
    # Whitespace-only text → render_layer returns None → no change
    assert np.array_equal(out, base)


def test_apply_layers_skips_image_layer_when_path_missing():
    base = _solid_rgba(16, 16, (10, 20, 30))
    layer = Layer(kind="image", params={"path": "/does/not/exist.png"})
    out = apply_layers(base, [layer])
    assert np.array_equal(out, base)


def test_apply_layers_image_layer_overlays(tmp_path):
    """Real image overlay on top of the base, normal blend, full opacity."""
    from PIL import Image
    overlay_path = tmp_path / "overlay.png"
    Image.fromarray(_solid_rgba(32, 32, (255, 0, 0))).save(str(overlay_path))

    base = _solid_rgba(32, 32, (0, 0, 255))
    layer = Layer(
        kind="image",
        opacity=1.0,
        blend_mode="normal",
        params={"path": str(overlay_path)},
    )
    out = apply_layers(base, [layer])
    # With opacity 1 and normal blend, the overlay's solid red wins entirely
    assert out[0, 0, 0] == 255  # R channel
    assert out[0, 0, 2] == 0    # B channel zeroed


# ---------------------------------------------------------------------------
# Blend modes
# ---------------------------------------------------------------------------


def _apply_via_image_layer(
    base_rgb: tuple[int, int, int],
    overlay_rgb: tuple[int, int, int],
    blend: str,
    tmp_path,
) -> np.ndarray:
    """Helper: composite a solid overlay over a solid base via apply_layers."""
    from PIL import Image
    overlay_path = tmp_path / f"ov_{blend}.png"
    Image.fromarray(_solid_rgba(8, 8, overlay_rgb)).save(str(overlay_path))
    layer = Layer(
        kind="image",
        opacity=1.0,
        blend_mode=blend,
        params={"path": str(overlay_path)},
    )
    return apply_layers(_solid_rgba(8, 8, base_rgb), [layer])


def test_multiply_darkens(tmp_path):
    out = _apply_via_image_layer((128, 128, 128), (128, 128, 128), "multiply", tmp_path)
    # 0.5 * 0.5 = 0.25 → ~64
    assert 60 <= out[0, 0, 0] <= 68


def test_screen_brightens(tmp_path):
    out = _apply_via_image_layer((128, 128, 128), (128, 128, 128), "screen", tmp_path)
    # 1 - (0.5)*(0.5) = 0.75 → ~191
    assert 188 <= out[0, 0, 0] <= 194


def test_overlay_passthrough_for_neutral_grey(tmp_path):
    """Overlay of 50% grey on 50% grey should stay roughly mid-grey."""
    out = _apply_via_image_layer((128, 128, 128), (128, 128, 128), "overlay", tmp_path)
    # base < 0.5 → low formula = 2*0.5*0.5 = 0.5 → 128
    assert 122 <= out[0, 0, 0] <= 134


def test_unknown_blend_mode_falls_back_to_normal(tmp_path):
    # Layer.from_dict normalises bogus blend_mode to "normal"
    layer = Layer.from_dict({
        "kind": "image",
        "blend_mode": "weird-mode",
        "params": {"path": str(tmp_path / "missing.png")},
    })
    assert layer.blend_mode == "normal"


def test_all_blend_modes_are_recognised():
    """No blend mode should raise — even private ones."""
    base = _solid_rgba(4, 4, (100, 100, 100))
    for mode in BLEND_MODES:
        # Using an image layer with missing path → render returns None,
        # so no actual blending happens, but we exercise the validation.
        layer = Layer(
            kind="image",
            blend_mode=mode,
            params={"path": "/does/not/exist"},
        )
        out = apply_layers(base, [layer])
        assert out.shape == base.shape


# ---------------------------------------------------------------------------
# Recipe integration
# ---------------------------------------------------------------------------


def test_recipe_with_only_layers_is_not_identity():
    from Imervue.image.recipe import Recipe
    r = Recipe()
    assert r.is_identity() is True
    r.extra["layers"] = [{"kind": "text", "params": {"text": "x"}}]
    assert r.is_identity() is False


def test_recipe_apply_runs_layer_stack(tmp_path):
    from Imervue.image.recipe import Recipe
    r = Recipe()
    r.extra["layers"] = [{
        "kind": "text",
        "params": {"text": "X", "corner": "center", "font_fraction": 0.3,
                   "color": [255, 0, 0], "shadow": False},
        "blend_mode": "normal",
        "opacity": 1.0,
        "enabled": True,
    }]
    base = _solid_rgba(64, 64, (50, 50, 50))
    out = r.apply(base)
    assert not np.array_equal(out, base)


# ---------------------------------------------------------------------------
# Dialog helpers (pure)
# ---------------------------------------------------------------------------


def test_move_layer_up_swaps():
    from Imervue.gui.layers_dialog import move_layer_up
    layers = [Layer(kind="text"), Layer(kind="image"), Layer(kind="lut")]
    new_idx = move_layer_up(layers, 2)
    assert new_idx == 1
    assert [lyr.kind for lyr in layers] == ["text", "lut", "image"]


def test_move_layer_up_at_top_is_noop():
    from Imervue.gui.layers_dialog import move_layer_up
    layers = [Layer(kind="text"), Layer(kind="image")]
    assert move_layer_up(layers, 0) == 0
    assert [lyr.kind for lyr in layers] == ["text", "image"]


def test_move_layer_down_swaps():
    from Imervue.gui.layers_dialog import move_layer_down
    layers = [Layer(kind="text"), Layer(kind="image"), Layer(kind="lut")]
    new_idx = move_layer_down(layers, 0)
    assert new_idx == 1
    assert [lyr.kind for lyr in layers] == ["image", "text", "lut"]


def test_move_layer_down_at_bottom_is_noop():
    from Imervue.gui.layers_dialog import move_layer_down
    layers = [Layer(kind="text"), Layer(kind="image")]
    assert move_layer_down(layers, 1) == 1
    assert [lyr.kind for lyr in layers] == ["text", "image"]


def test_add_default_layer_respects_max():
    from Imervue.gui.layers_dialog import add_default_layer
    layers: list[Layer] = []
    for _ in range(MAX_LAYERS):
        added = add_default_layer(layers, "text")
        assert added is not None
    overflow = add_default_layer(layers, "text")
    assert overflow is None
    assert len(layers) == MAX_LAYERS


def test_add_default_layer_normalises_unknown_kind():
    from Imervue.gui.layers_dialog import add_default_layer
    layers: list[Layer] = []
    add_default_layer(layers, "garbage")
    assert layers[0].kind == "text"


# ---------------------------------------------------------------------------
# Dialog smoke (Qt)
# ---------------------------------------------------------------------------


def test_dialog_opens_and_loads_existing_layers(qapp):
    from Imervue.gui.layers_dialog import LayersDialog
    from Imervue.image.recipe import Recipe
    recipe = Recipe()
    recipe.extra["layers"] = [
        {"kind": "text", "params": {"text": "first"}},
        {"kind": "image", "params": {"path": "/var/data/x.png"}},
    ]
    dlg = LayersDialog(recipe)
    assert dlg._list.count() == 2


def test_dialog_emits_serialised_layers_on_apply(qapp):
    from Imervue.gui.layers_dialog import LayersDialog
    from Imervue.image.recipe import Recipe
    captured = {}
    dlg = LayersDialog(Recipe())
    dlg._add_layer()  # adds one default text layer
    dlg.layers_changed.connect(lambda lst: captured.update(value=lst))
    dlg._apply()
    assert "value" in captured
    assert isinstance(captured["value"], list)
    assert len(captured["value"]) == 1
    assert captured["value"][0]["kind"] == "text"
