"""Contract tests pinning the paint layer compositor's observable behaviour.

Every expected buffer below was recorded from the compositor before it was
split into sibling modules. Results are compared as uint8 with a one-level
tolerance so a float32 rounding difference between platforms cannot flip a
truncated channel into a false failure.
"""
from __future__ import annotations

import re

import numpy as np
import pytest

from Imervue.paint import compositing
from Imervue.paint.blend_if import BlendIf
from Imervue.paint.blend_modes import BLEND_MODES
from Imervue.paint.compositing import (
    LAYER_BLEND_MODES,
    composite_layer_pair,
    composite_region,
    composite_stack,
)
from Imervue.paint.layer_model import Layer, LayerGroup

_H, _W = 2, 3
_SHAPE = (_H, _W)


def _ramp(offset: int, alpha: list[int]) -> np.ndarray:
    rgb = (np.arange(_H * _W * 3).reshape(_H, _W, 3) * 37 + offset) % 256
    a = np.array(alpha, dtype=np.uint8).reshape(_H, _W, 1)
    return np.concatenate([rgb.astype(np.uint8), a], axis=2)


_BELOW = _ramp(11, [255, 200, 128, 64, 0, 255])
_ABOVE = _ramp(90, [255, 255, 180, 90, 200, 0])
_THIRD = _ramp(170, [140, 255, 255, 30, 255, 220])
_MASK = np.array([[255, 128, 0], [64, 255, 200]], dtype=np.uint8)


def _assert_close(actual: np.ndarray, expected: tuple[int, ...]) -> None:
    assert actual.dtype == np.uint8
    want = np.array(expected, dtype=np.int16).reshape(actual.shape)
    diff = np.abs(actual.astype(np.int16) - want)
    assert int(diff.max()) <= 1, f"got {tuple(int(v) for v in actual.ravel())}"


# ---------------------------------------------------------------------------
# Spies for the lazily imported per-layer render hooks
# ---------------------------------------------------------------------------


class _Calls:
    def __init__(self) -> None:
        self.log: list[str] = []


def _install_spies(monkeypatch) -> _Calls:
    calls = _Calls()

    def tone(image, settings):
        calls.log.append(f"tone:{settings}")
        out = image.copy()
        out[..., :3] = out[..., :3] // 2
        return out

    def binary(image, settings):
        calls.log.append(f"binary:{settings}")
        out = image.copy()
        out[..., 3] = np.where(out[..., 0] > 60, 255, 0).astype(np.uint8)
        return out

    def effects(image, fx):
        calls.log.append(f"effects:{len(fx)}")
        return np.roll(image, 1, axis=1)

    def adjust(image, adjustment):
        calls.log.append(f"adjust:{adjustment}")
        out = image.copy()
        out[..., :3] = 255 - out[..., :3]
        return out

    def realise(layer):
        calls.log.append(f"vector:{layer.name}")
        layer.image[..., 2] = 7
        return True

    monkeypatch.setattr("Imervue.paint.halftone.render_tone_layer", tone)
    monkeypatch.setattr("Imervue.paint.binary_layer.render_binary_layer", binary)
    monkeypatch.setattr("Imervue.paint.layer_effects.apply_effects", effects)
    monkeypatch.setattr("Imervue.paint.adjustments.apply_adjustment", adjust)
    monkeypatch.setattr("Imervue.paint.vector_layer.realise_vector_layer", realise)
    return calls


@pytest.fixture
def spies(monkeypatch) -> _Calls:
    return _install_spies(monkeypatch)


# ---------------------------------------------------------------------------
# Scenario stacks
# ---------------------------------------------------------------------------


def _mixed_stack() -> tuple[list[Layer], dict]:
    layers = [
        Layer(name="base", image=_BELOW.copy()),
        Layer(name="hidden", image=_THIRD.copy(), visible=False),
        Layer(
            name="grouped", image=_ABOVE.copy(), opacity=0.8,
            blend_mode="multiply", mask=_MASK.copy(), group="g",
        ),
        Layer(
            name="clipped", image=_THIRD.copy(), opacity=0.9,
            blend_mode="screen", clip=True,
        ),
        Layer(name="in_hidden_group", image=_THIRD.copy(), group="hid"),
        Layer(
            name="gated", image=_THIRD.copy(), blend_mode="overlay",
            blend_if=BlendIf(this_min=40, this_max=220, this_min_feather=20),
        ),
        Layer(
            name="clip_mask", image=_ABOVE.copy(), opacity=0.7,
            clip=True, mask=_MASK.copy(), blend_mode="darken",
        ),
        Layer(
            name="masked_gate", image=_BELOW.copy(), opacity=0.6,
            blend_mode="lighten", mask=_MASK[::-1].copy(),
            blend_if=BlendIf(underlying_min=30, underlying_max=230),
        ),
        Layer(
            name="disabled_mask", image=_THIRD.copy(), opacity=0.5,
            blend_mode="linear_burn", mask=np.zeros(_SHAPE, np.uint8),
            mask_enabled=False,
        ),
    ]
    groups = {
        "g": LayerGroup("g", opacity=0.5),
        "hid": LayerGroup("hid", visible=False),
        "unused": LayerGroup("unused", opacity=0.1),
    }
    return layers, groups


def _clip_at_bottom_stack() -> tuple[list[Layer], dict]:
    layers = [
        Layer(name="orphan_clip", image=_ABOVE.copy(), clip=True, blend_mode="soft_light"),
        Layer(name="second", image=_THIRD.copy(), opacity=0.65, blend_mode="hard_light"),
        Layer(name="zero_group", image=_BELOW.copy(), group="zero"),
        Layer(name="dodge", image=_BELOW.copy(), blend_mode="color_dodge", group="half"),
    ]
    groups = {
        "zero": LayerGroup("zero", opacity=0.0),
        "half": LayerGroup("half", opacity=0.4, blend_mode="multiply"),
    }
    return layers, groups


def _render_hook_stack() -> list[Layer]:
    return [
        Layer(name="base", image=_BELOW.copy()),
        Layer(
            name="vec", image=_ABOVE.copy(), blend_mode="linear_dodge",
            vector_data="strokes", tone="T", binary="B",
        ),
        Layer(name="toned", image=_THIRD.copy(), opacity=0.5, tone="T2"),
    ]


_EXPECTED_PAIR: dict[str, tuple[int, ...]] = {
    "normal": (
        70, 107, 144, 255, 156, 193, 119, 220, 233, 14, 51, 128, 105, 142, 179, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "multiply": (
        5, 29, 62, 255, 120, 162, 117, 220, 233, 14, 51, 128, 99, 136, 174, 76, 22, 58,
        96, 150, 54, 91, 128, 255,
    ),
    "screen": (
        75, 125, 166, 255, 165, 196, 180, 220, 233, 14, 51, 128, 107, 143, 179, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "overlay": (
        8, 47, 103, 255, 153, 194, 162, 220, 233, 14, 51, 128, 102, 142, 179, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "darken": (
        11, 48, 85, 255, 129, 166, 119, 220, 233, 14, 51, 128, 101, 138, 175, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "lighten": (
        70, 107, 144, 255, 156, 193, 179, 220, 233, 14, 51, 128, 105, 142, 179, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "color_dodge": (
        15, 83, 199, 255, 174, 199, 184, 220, 233, 14, 51, 128, 110, 145, 180, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "color_burn": (
        2, 12, 21, 255, 117, 164, 112, 220, 233, 14, 51, 128, 96, 136, 174, 76, 22, 58,
        96, 150, 54, 91, 128, 255,
    ),
    "soft_light": (
        8, 47, 98, 255, 140, 178, 166, 220, 233, 14, 51, 128, 102, 139, 177, 76, 22, 58,
        96, 150, 54, 91, 128, 255,
    ),
    "hard_light": (
        8, 47, 121, 255, 155, 194, 122, 220, 233, 14, 51, 128, 103, 142, 179, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
    "linear_burn": (
        2, 12, 21, 255, 110, 160, 112, 220, 233, 14, 51, 128, 96, 135, 174, 76, 22, 58,
        96, 150, 54, 91, 128, 255,
    ),
    "linear_dodge": (
        78, 143, 208, 255, 174, 199, 185, 220, 233, 14, 51, 128, 110, 145, 180, 76, 22,
        58, 96, 150, 54, 91, 128, 255,
    ),
}
_EXPECTED_MIXED = (
    74, 137, 185, 255, 34, 67, 73, 255, 140, 138, 201, 255, 144, 92, 131, 128, 24, 48,
    102, 255, 66, 163, 25, 255,
)
_EXPECTED_CLIP_AT_BOTTOM = (
    110, 169, 217, 255, 122, 188, 32, 255, 117, 137, 194, 233, 176, 172, 208, 117, 31,
    80, 141, 235, 187, 213, 63, 187,
)
_EXPECTED_ADJUSTMENT = (
    255, 255, 200, 255, 140, 112, 251, 255, 210, 195, 178, 217, 120, 95, 71, 131, 233,
    196, 159, 200, 128, 128, 128, 255,
)
_EXPECTED_HOOKS = (
    31, 63, 95, 255, 103, 128, 102, 255, 123, 61, 86, 191, 106, 126, 42, 255, 51, 69,
    88, 127, 113, 154, 80, 255,
)
_EXPECTED_EFFECTS = (
    122, 151, 179, 221, 65, 109, 149, 255, 158, 184, 152, 255, 247, 28, 65, 10, 116,
    150, 183, 219, 11, 29, 48, 200,
)


# ---------------------------------------------------------------------------
# Blend-mode registry
# ---------------------------------------------------------------------------


def test_layer_blend_modes_is_the_shared_registry_in_order():
    assert LAYER_BLEND_MODES is BLEND_MODES
    assert LAYER_BLEND_MODES == (
        "normal", "multiply", "screen", "overlay",
        "darken", "lighten",
        "color_dodge", "color_burn",
        "soft_light", "hard_light",
        "linear_burn", "linear_dodge",
    )


def test_public_names_stay_importable_from_compositing():
    for name in (
        "LAYER_BLEND_MODES", "composite_layer_pair",
        "composite_stack", "composite_region",
    ):
        assert hasattr(compositing, name)


# ---------------------------------------------------------------------------
# composite_layer_pair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", BLEND_MODES)
def test_pair_output_for_every_blend_mode(mode):
    out = composite_layer_pair(_BELOW, _ABOVE, opacity=0.75, blend_mode=mode, mask=_MASK)
    _assert_close(out, _EXPECTED_PAIR[mode])


def test_pair_does_not_mutate_inputs():
    below, above, mask = _BELOW.copy(), _ABOVE.copy(), _MASK.copy()
    composite_layer_pair(below, above, opacity=0.5, blend_mode="screen", mask=mask)
    assert np.array_equal(below, _BELOW)
    assert np.array_equal(above, _ABOVE)
    assert np.array_equal(mask, _MASK)


@pytest.mark.parametrize("opacity", [0.0, -2.0])
def test_pair_zero_opacity_returns_a_copy_of_below(opacity):
    out = composite_layer_pair(_BELOW, _ABOVE, opacity=opacity)
    assert out is not _BELOW
    assert np.array_equal(out, _BELOW)


def test_pair_zero_opacity_skips_mask_validation():
    bad = np.zeros((5, 5), dtype=np.float32)
    out = composite_layer_pair(_BELOW, _ABOVE, opacity=0.0, mask=bad)
    assert np.array_equal(out, _BELOW)


def test_pair_opacity_above_one_is_clamped():
    a = composite_layer_pair(_BELOW, _ABOVE, opacity=7.0, blend_mode="overlay")
    b = composite_layer_pair(_BELOW, _ABOVE, opacity=1.0, blend_mode="overlay")
    assert np.array_equal(a, b)


def test_pair_full_mask_equals_no_mask():
    full = np.full(_SHAPE, 255, dtype=np.uint8)
    a = composite_layer_pair(_BELOW, _ABOVE, opacity=0.4, blend_mode="color_burn", mask=full)
    b = composite_layer_pair(_BELOW, _ABOVE, opacity=0.4, blend_mode="color_burn")
    assert np.array_equal(a, b)


def test_pair_transparent_over_transparent_stays_zero():
    clear = np.zeros((1, 2, 4), dtype=np.uint8)
    out = composite_layer_pair(clear, clear, blend_mode="color_dodge")
    assert np.array_equal(out, clear)


def test_pair_unknown_blend_mode_message():
    with pytest.raises(ValueError, match=r"unknown blend_mode 'glow'; expected one of \("):
        composite_layer_pair(_BELOW, _ABOVE, blend_mode="glow")


def test_pair_shape_check_runs_before_blend_mode_check():
    with pytest.raises(ValueError, match="below must be HxWx4 uint8 RGBA"):
        composite_layer_pair(_BELOW[..., :3], _ABOVE, blend_mode="glow")


@pytest.mark.parametrize(
    "below",
    [
        np.zeros((2, 3), np.uint8),
        np.zeros((2, 3, 3), np.uint8),
        np.zeros((2, 3, 4), np.float32),
    ],
)
def test_pair_rejects_bad_below(below):
    with pytest.raises(
        ValueError,
        match=re.escape(f"below must be HxWx4 uint8 RGBA, got {below.shape} {below.dtype}"),
    ):
        composite_layer_pair(below, _ABOVE)


@pytest.mark.parametrize(
    "above",
    [np.zeros((2, 2, 4), np.uint8), np.zeros((2, 3, 4), np.uint16)],
)
def test_pair_rejects_mismatched_above(above):
    with pytest.raises(ValueError, match="above must match below shape/dtype: got"):
        composite_layer_pair(_BELOW, above)


def test_pair_rejects_mask_shape():
    with pytest.raises(
        ValueError, match=r"mask shape \(3, 2\) does not match canvas \(2, 3\)",
    ):
        composite_layer_pair(_BELOW, _ABOVE, mask=np.zeros((3, 2), np.uint8))


def test_pair_rejects_mask_dtype():
    with pytest.raises(ValueError, match="mask dtype must be uint8, got float32"):
        composite_layer_pair(_BELOW, _ABOVE, mask=np.zeros(_SHAPE, np.float32))


# ---------------------------------------------------------------------------
# composite_stack
# ---------------------------------------------------------------------------


def test_stack_mixed_groups_clips_masks_and_blend_if():
    layers, groups = _mixed_stack()
    _assert_close(composite_stack(layers, _SHAPE, groups), _EXPECTED_MIXED)


def test_stack_clip_at_bottom_and_group_opacity():
    layers, groups = _clip_at_bottom_stack()
    _assert_close(composite_stack(layers, _SHAPE, groups), _EXPECTED_CLIP_AT_BOTTOM)


def test_stack_groups_none_treats_group_names_as_ungrouped():
    layers, _ = _clip_at_bottom_stack()
    ungrouped = [Layer(name=lyr.name, image=lyr.image, opacity=lyr.opacity,
                       blend_mode=lyr.blend_mode, clip=lyr.clip) for lyr in layers]
    assert np.array_equal(
        composite_stack(layers, _SHAPE), composite_stack(ungrouped, _SHAPE),
    )


def test_stack_adjustment_layers(spies):
    layers = [
        Layer(name="base", image=_BELOW.copy()),
        Layer(name="adj_half", image=_THIRD.copy(), opacity=0.5, adjustment="A1"),
        Layer(name="burn", image=_ABOVE.copy(), blend_mode="color_burn"),
        Layer(name="adj_full", image=np.zeros((1, 1, 4), np.uint8), adjustment="A2"),
        Layer(name="adj_hidden", image=_THIRD.copy(), visible=False, adjustment="A3"),
    ]
    out = composite_stack(layers, _SHAPE)
    _assert_close(out, _EXPECTED_ADJUSTMENT)
    assert spies.log == ["adjust:A1", "adjust:A2"]


def test_stack_adjustment_does_not_become_clip_base(spies):
    layers = [
        Layer(name="base", image=_ABOVE.copy()),
        Layer(name="adj", image=np.zeros((2, 3, 4), np.uint8), adjustment="A"),
        Layer(name="clip", image=_THIRD.copy(), clip=True),
    ]
    out = composite_stack(layers, _SHAPE)
    assert spies.log == ["adjust:A"]
    step = composite_layer_pair(np.zeros_like(_ABOVE), _ABOVE)
    step[..., :3] = 255 - step[..., :3]
    expected = composite_layer_pair(step, _THIRD, mask=_ABOVE[..., 3].copy())
    assert np.array_equal(out, expected)


def test_stack_render_hooks_order_and_output(spies):
    out = composite_stack(_render_hook_stack(), _SHAPE)
    _assert_close(out, _EXPECTED_HOOKS)
    assert spies.log == ["vector:vec", "tone:T", "binary:B", "tone:T2"]


def test_stack_effects_and_clip_base_uses_raw_image_alpha(spies):
    layers = [
        Layer(name="fx", image=_ABOVE.copy(), effects=("shadow", "glow"), tone="T"),
        Layer(name="clip", image=_THIRD.copy(), clip=True, blend_mode="screen"),
    ]
    out = composite_stack(layers, _SHAPE)
    _assert_close(out, _EXPECTED_EFFECTS)
    assert spies.log == ["tone:T", "effects:2"]


def test_stack_empty_and_all_hidden_are_transparent():
    assert np.array_equal(composite_stack([], _SHAPE), np.zeros((2, 3, 4), np.uint8))
    hidden = [Layer(name="h", image=_ABOVE.copy(), visible=False)]
    assert np.array_equal(composite_stack(hidden, _SHAPE), np.zeros((2, 3, 4), np.uint8))
    zero = [Layer(name="z", image=_ABOVE.copy(), opacity=0.0)]
    assert np.array_equal(composite_stack(zero, _SHAPE), np.zeros((2, 3, 4), np.uint8))


@pytest.mark.parametrize("kwargs", [{}, {"clip": True}, {"group": "g"}])
def test_stack_single_plain_layer_is_returned_as_is(kwargs):
    layer = Layer(name="only", image=_ABOVE.copy(), **kwargs)
    if "group" in kwargs:
        assert composite_stack([layer], _SHAPE) is not layer.image
    else:
        assert composite_stack([layer], _SHAPE) is layer.image


def test_stack_single_layer_fast_path_realises_vectors(spies):
    layer = Layer(name="only", image=_ABOVE.copy(), vector_data="v")
    out = composite_stack(iter([layer]), _SHAPE)
    assert out is layer.image
    assert spies.log == ["vector:only"]
    assert int(out[0, 0, 2]) == 7


@pytest.mark.parametrize(
    "kwargs",
    [
        {"opacity": 0.5}, {"blend_mode": "screen"}, {"mask": _MASK},
        {"group": "g"},
    ],
)
def test_stack_single_layer_slow_path_returns_new_buffer(kwargs):
    layer = Layer(name="only", image=_ABOVE.copy(), **kwargs)
    out = composite_stack([layer], _SHAPE, {"g": LayerGroup("g")})
    assert out is not layer.image
    expected = composite_layer_pair(
        np.zeros((2, 3, 4), np.uint8), _ABOVE,
        opacity=kwargs.get("opacity", 1.0),
        blend_mode=kwargs.get("blend_mode", "normal"),
        mask=kwargs.get("mask"),
    )
    assert np.array_equal(out, expected)


def test_stack_single_hidden_group_layer_is_skipped():
    layer = Layer(name="only", image=_ABOVE.copy(), group="g")
    out = composite_stack([layer], _SHAPE, {"g": LayerGroup("g", visible=False)})
    assert np.array_equal(out, np.zeros((2, 3, 4), np.uint8))


def test_stack_shape_mismatch_message():
    layers = [Layer(name="base", image=_ABOVE.copy()), Layer(name="odd", image=_ABOVE[:, :2].copy())]
    with pytest.raises(
        ValueError, match=r"layer 'odd' shape \(2, 2\) does not match document \(2, 3\)",
    ):
        composite_stack(layers, _SHAPE)


def test_stack_single_layer_shape_mismatch_falls_to_slow_path_error():
    with pytest.raises(ValueError, match="layer 'odd' shape"):
        composite_stack([Layer(name="odd", image=_ABOVE[:, :2].copy())], _SHAPE)


def test_stack_hidden_layer_shape_is_not_checked():
    layers = [Layer(name="base", image=_ABOVE.copy()),
              Layer(name="odd", image=_ABOVE[:, :2].copy(), visible=False)]
    assert composite_stack(layers, _SHAPE).shape == (2, 3, 4)


# ---------------------------------------------------------------------------
# composite_region
# ---------------------------------------------------------------------------


_RECTS = [(0, 0, 3, 2), (1, 0, 2, 2), (0, 1, 3, 1), (2, 1, 1, 1)]


@pytest.mark.parametrize("rect", _RECTS)
@pytest.mark.parametrize("builder", [_mixed_stack, _clip_at_bottom_stack])
def test_region_matches_full_stack_slice(rect, builder):
    layers, groups = builder()
    full = composite_stack(layers, _SHAPE, groups)
    layers, groups = builder()
    region = composite_region(layers, _SHAPE, rect, groups)
    x, y, rw, rh = rect
    assert region.shape == (rh, rw, 4)
    assert np.array_equal(region, full[y:y + rh, x:x + rw])


@pytest.mark.parametrize("rect", _RECTS)
def test_region_render_hooks_match_full_stack(spies, rect):
    full = composite_stack(_render_hook_stack(), _SHAPE)
    spies.log.clear()
    region = composite_region(_render_hook_stack(), _SHAPE, rect)
    x, y, rw, rh = rect
    assert np.array_equal(region, full[y:y + rh, x:x + rw])
    assert spies.log == ["vector:vec", "tone:T", "binary:B", "tone:T2"]


def test_region_single_layer_does_not_take_the_fast_path():
    layer = Layer(name="only", image=_ABOVE.copy())
    region = composite_region([layer], _SHAPE, (0, 0, 3, 2))
    assert region is not layer.image
    assert np.array_equal(region, composite_layer_pair(np.zeros_like(_ABOVE), _ABOVE))


def test_region_empty_stack_returns_full_canvas_even_for_bad_rect():
    out = composite_region([], _SHAPE, (5, 5, 0, 0))
    assert np.array_equal(out, np.zeros((2, 3, 4), np.uint8))


@pytest.mark.parametrize(
    "rect",
    [(0, 0, 0, 2), (0, 0, 3, 0), (-1, 0, 2, 2), (0, -1, 2, 2), (1, 0, 3, 2), (0, 1, 3, 2)],
)
def test_region_rejects_rect_outside_canvas(rect):
    layers = [Layer(name="base", image=_ABOVE.copy())]
    assert composite_region(layers, _SHAPE, rect) is None


@pytest.mark.parametrize(
    "extra",
    [{"effects": ("glow",)}, {"adjustment": "A"}, {"adjustment": "A", "visible": False}],
)
def test_region_refuses_context_dependent_layers(extra):
    layers = [Layer(name="base", image=_ABOVE.copy()), Layer(name="x", image=_THIRD.copy(), **extra)]
    assert composite_region(layers, _SHAPE, (0, 0, 1, 1)) is None


def test_region_refuses_mismatched_layer_shape_even_when_hidden():
    layers = [Layer(name="base", image=_ABOVE.copy()),
              Layer(name="odd", image=_ABOVE[:, :2].copy(), visible=False)]
    assert composite_region(layers, _SHAPE, (0, 0, 1, 1)) is None
