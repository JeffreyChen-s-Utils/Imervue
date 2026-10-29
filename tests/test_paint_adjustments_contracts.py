"""Contract tests for the paint adjustment registry and every adjustment kind.

They pin the registry contents and order, the exact output pixels of each
kind (default and clamped parameters) and the validation errors, so the
kinds can move between modules without any observable change.
"""
from __future__ import annotations

import dataclasses
import hashlib

import numpy as np
import pytest

from Imervue.paint import adjustments
from Imervue.paint.adjustments import (
    ADJUSTMENT_KINDS,
    DEFAULT_PARAMS,
    SELECTIVE_RANGE_CENTERS,
    SELECTIVE_RANGES,
    Adjustment,
    apply_adjustment,
)


def _grid() -> np.ndarray:
    """A deterministic 16x16 RGBA image that walks every hue band."""
    idx = np.arange(256, dtype=np.int64).reshape(16, 16)
    return np.stack(
        [idx, (idx * 7) % 256, (idx * 13 + 50) % 256, (idx * 3) % 256],
        axis=-1,
    ).astype(np.uint8)


def _digest(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()[:16]


_CASES: list[tuple[str, str, dict]] = [
    ("levels-default", "levels", {}),
    ("levels-tuned", "levels", {
        "input_black": 20, "input_white": 230, "gamma": 2.0,
        "output_black": 10, "output_white": 240,
    }),
    ("levels-clamped", "levels", {
        "input_black": -5, "input_white": 0, "gamma": 1.0,
        "output_black": 999, "output_white": -3,
    }),
    ("curves-default", "curves", {}),
    ("curves-tuned", "curves", {
        "points": [[0, 10], [128, 200], [255, 240]],
        "points_r": [[0, 255], [255, 0]],
        "points_g": [[1]],
        "points_b": None,
    }),
    ("curves-bad-base", "curves", {"points": [[300, -40], "junk"]}),
    ("hsv-default", "hsv", {}),
    ("hsv-tuned", "hsv", {"hue_shift_deg": 90.0, "saturation": 1.5, "lightness": 0.8}),
    ("hsv-clamped", "hsv", {"hue_shift_deg": -400.0, "saturation": 99.0, "lightness": -1.0}),
    ("bc-default", "brightness_contrast", {}),
    ("bc-tuned", "brightness_contrast", {"brightness": 0.2, "contrast": 0.5}),
    ("bc-clamped", "brightness_contrast", {"brightness": 5.0, "contrast": -5.0}),
    ("cb-default", "color_balance", {}),
    ("cb-tuned", "color_balance", {
        "shadows": [0.1, -0.2, 0.3],
        "midtones": [5, "x", -0.1],
        "highlights": "bad",
    }),
    ("sel-default", "selective_color", {}),
    ("sel-tuned", "selective_color", {
        "range": "blues", "width_deg": 90.0, "hue_shift_deg": 30.0,
        "saturation_delta": 0.3, "lightness_delta": -0.2,
    }),
    ("sel-clamped", "selective_color", {
        "range": "purple", "width_deg": 0.0, "hue_shift_deg": 45.0,
        "saturation_delta": 9.0, "lightness_delta": -9.0,
    }),
    ("pf-default", "photo_filter", {}),
    ("pf-tuned", "photo_filter", {"color": [0, 128, 255, 9], "density": 0.6}),
    ("pf-bad-color", "photo_filter", {"color": "x", "density": 2.0}),
    ("pf-zero", "photo_filter", {"density": 0.0}),
    ("hsl-default", "hsl", {}),
    ("hsl-tuned", "hsl", {"hue_shift_deg": -45.0, "saturation": 0.5, "lightness": 1.2}),
    ("hsl-clamped", "hsl", {"saturation": 50.0, "lightness": -2.0}),
    ("gm-default", "gradient_map", {}),
    ("gm-tuned", "gradient_map", {"stops": [
        {"position": 1.0, "color": [255, 220, 0]},
        {"position": 0.0},
        {"position": 0.5, "color": [200, 0, 80, 10]},
        {"position": "bad", "color": [1, 2, 3]},
        {"position": 0.25, "color": [1, 2]},
        {"position": 0.75, "color": ["x", 2, 3]},
        "not-a-dict",
    ]}),
    ("gm-one-stop", "gradient_map", {"stops": [
        {"position": 0.3, "color": [255, 0, 0]},
    ]}),
    ("gm-clamped", "gradient_map", {"stops": [
        {"position": -2.0, "color": [-50, 300, 128, 999]},
        {"position": 7.0, "color": [10, 20, 30]},
    ]}),
    ("cm-default", "channel_mixer", {}),
    ("cm-tuned", "channel_mixer", {
        "output_red": [0.5, 0.3, 0.2, 0.1],
        "output_green": [9.0, "x", -9.0, 0.0],
        "output_blue": [1.0, 0.0],
    }),
    ("post-default", "posterize", {}),
    ("post-3", "posterize", {"levels": 3}),
    ("post-low", "posterize", {"levels": 1}),
    ("post-high", "posterize", {"levels": 999}),
    ("thr-default", "threshold", {}),
    ("thr-100", "threshold", {"threshold": 100}),
    ("thr-low", "threshold", {"threshold": -5}),
    ("thr-high", "threshold", {"threshold": 999}),
]

_EXPECTED: dict[str, str] = {
    "levels-default": "bae4821030386e78",
    "levels-tuned": "53f7cda28fbe6984",
    "levels-clamped": "b8a9fe295b6c2ce4",
    "curves-default": "bae4821030386e78",
    "curves-tuned": "9c5b72026ef7a8c4",
    "curves-bad-base": "bae4821030386e78",
    "hsv-default": "23a3706848f25c66",
    "hsv-tuned": "78ce2dc3d5e93659",
    "hsv-clamped": "88fdc3f4485a6b6e",
    "bc-default": "66bf433431f43a17",
    "bc-tuned": "0334375e3a0eeff1",
    "bc-clamped": "174feecf9526bb35",
    "cb-default": "bae4821030386e78",
    "cb-tuned": "9d6b111746add4b4",
    "sel-default": "23a3706848f25c66",
    "sel-tuned": "c0e9e7dd1cfce109",
    "sel-clamped": "ad1c0ae844c97c1a",
    "pf-default": "9c77ed6c8757a7ac",
    "pf-tuned": "1f13c8a21b9bee1d",
    "pf-bad-color": "fd7964072dc7cf20",
    "pf-zero": "bae4821030386e78",
    "hsl-default": "f9070f4951ca42db",
    "hsl-tuned": "58644437f7dbf516",
    "hsl-clamped": "88fdc3f4485a6b6e",
    "gm-default": "1633a9f4c3712885",
    "gm-tuned": "acb4d2f38d01c3ea",
    "gm-one-stop": "1633a9f4c3712885",
    "gm-clamped": "fd0c4739c3ab3790",
    "cm-default": "bae4821030386e78",
    "cm-tuned": "660558350b4a88ca",
    "post-default": "b1df6c88352d459e",
    "post-3": "ba580dc2e610fd5d",
    "post-low": "806e37674e43afc3",
    "post-high": "bae4821030386e78",
    "thr-default": "7e3b4d9b4bde166a",
    "thr-100": "9b408a9c3bb507a7",
    "thr-low": "174feecf9526bb35",
    "thr-high": "88fdc3f4485a6b6e",
}


def test_registry_kinds_and_order():
    assert ADJUSTMENT_KINDS == (
        "levels", "curves", "hsv", "brightness_contrast", "color_balance",
        "selective_color", "photo_filter", "hsl", "gradient_map",
        "channel_mixer", "posterize", "threshold",
    )
    assert tuple(DEFAULT_PARAMS) == ADJUSTMENT_KINDS


def test_registry_default_param_keys():
    assert {kind: list(params) for kind, params in DEFAULT_PARAMS.items()} == {
        "levels": ["input_black", "input_white", "gamma", "output_black", "output_white"],
        "curves": ["points"],
        "hsv": ["hue_shift_deg", "saturation", "lightness"],
        "brightness_contrast": ["brightness", "contrast"],
        "color_balance": ["shadows", "midtones", "highlights"],
        "selective_color": [
            "range", "width_deg", "hue_shift_deg",
            "saturation_delta", "lightness_delta",
        ],
        "photo_filter": ["color", "density"],
        "hsl": ["hue_shift_deg", "saturation", "lightness"],
        "gradient_map": ["stops"],
        "channel_mixer": ["output_red", "output_green", "output_blue"],
        "posterize": ["levels"],
        "threshold": ["threshold"],
    }
    assert DEFAULT_PARAMS["photo_filter"]["color"] == [235, 165, 95]
    assert DEFAULT_PARAMS["threshold"]["threshold"] == 128


def test_selective_ranges_and_centres():
    assert SELECTIVE_RANGES == ("reds", "yellows", "greens", "cyans", "blues", "magentas")
    assert list(SELECTIVE_RANGE_CENTERS.items()) == [
        ("reds", 0.0), ("yellows", 60.0), ("greens", 120.0),
        ("cyans", 180.0), ("blues", 240.0), ("magentas", 300.0),
    ]


def test_every_kind_has_a_case():
    assert {kind for _, kind, _ in _CASES} == set(ADJUSTMENT_KINDS)


@pytest.mark.parametrize(("case_id", "kind", "params"), _CASES, ids=[c[0] for c in _CASES])
def test_output_pixels_are_pinned(case_id, kind, params):
    image = _grid()
    out = apply_adjustment(image, Adjustment(kind=kind, params=params))
    assert out.shape == image.shape
    assert out.dtype == np.uint8
    assert out is not image
    np.testing.assert_array_equal(out[..., 3], image[..., 3])
    np.testing.assert_array_equal(image, _grid())
    assert _digest(out) == _EXPECTED[case_id]


@pytest.mark.parametrize("kind", ADJUSTMENT_KINDS)
def test_random_input_keeps_alpha_and_input(kind, sample_rgba_array):
    before = sample_rgba_array.copy()
    out = apply_adjustment(sample_rgba_array, Adjustment(kind=kind))
    assert out is not sample_rgba_array
    np.testing.assert_array_equal(out[..., 3], before[..., 3])
    np.testing.assert_array_equal(sample_rgba_array, before)


def test_default_params_are_identity_where_documented(sample_rgba_array):
    for kind in ("levels", "curves", "color_balance", "channel_mixer"):
        out = apply_adjustment(sample_rgba_array, Adjustment(kind=kind))
        np.testing.assert_array_equal(out, sample_rgba_array, err_msg=kind)


def test_photo_filter_zero_density_returns_a_copy():
    image = _grid()
    out = apply_adjustment(image, Adjustment(kind="photo_filter", params={"density": 0}))
    assert out is not image
    np.testing.assert_array_equal(out, image)


def test_threshold_outputs_only_black_or_white():
    out = apply_adjustment(_grid(), Adjustment(kind="threshold", params={"threshold": 90}))
    assert set(np.unique(out[..., :3]).tolist()) <= {0, 255}
    np.testing.assert_array_equal(out[..., 0], out[..., 1])
    np.testing.assert_array_equal(out[..., 1], out[..., 2])


@pytest.mark.parametrize("bad", [
    np.zeros((4, 4, 3), dtype=np.uint8),
    np.zeros((4, 4), dtype=np.uint8),
    np.zeros((4, 4, 4), dtype=np.float32),
])
def test_apply_rejects_non_rgba_uint8(bad):
    with pytest.raises(ValueError, match=r"^image must be HxWx4 uint8 RGBA, got "):
        apply_adjustment(bad, Adjustment(kind="levels"))


def test_image_is_validated_before_the_kind():
    adj = Adjustment(kind="levels")
    object.__setattr__(adj, "kind", "nope")
    with pytest.raises(ValueError, match="image must be"):
        apply_adjustment(np.zeros((2, 2, 3), dtype=np.uint8), adj)


def test_apply_rejects_unknown_kind_that_bypassed_validation():
    adj = Adjustment(kind="levels")
    object.__setattr__(adj, "kind", "nope")
    with pytest.raises(ValueError, match=r"^unknown adjustment kind 'nope'$"):
        apply_adjustment(_grid(), adj)


def test_adjustment_rejects_unknown_kind_and_bad_params():
    with pytest.raises(ValueError, match=r"^unknown adjustment kind 'blur'; expected one of"):
        Adjustment(kind="blur")
    with pytest.raises(ValueError, match=r"^params must be a dict, got list$"):
        Adjustment(kind="levels", params=[])


def test_adjustment_is_frozen():
    adj = Adjustment(kind="hsv")
    with pytest.raises(dataclasses.FrozenInstanceError):
        adj.kind = "hsl"


def test_from_dict_merges_defaults_and_round_trips():
    adj = Adjustment.from_dict({"kind": " posterize ", "params": {"levels": 6, "extra": 1}})
    assert adj == Adjustment(kind="posterize", params={"levels": 6, "extra": 1})
    assert Adjustment.from_dict(adj.to_dict()) == adj
    payload = adj.to_dict()
    assert payload == {"kind": "posterize", "params": {"levels": 6, "extra": 1}}
    assert payload["params"] is not adj.params


def test_from_dict_bad_params_fall_back_to_defaults():
    adj = Adjustment.from_dict({"kind": "threshold", "params": "junk"})
    assert adj.params == {"threshold": 128}
    assert adj.params is not DEFAULT_PARAMS["threshold"]


@pytest.mark.parametrize(("raw", "message"), [
    ([], r"^adjustment payload must be a dict, got list$"),
    ({}, r"^unknown adjustment kind ''$"),
    ({"kind": "blur"}, r"^unknown adjustment kind 'blur'$"),
])
def test_from_dict_errors(raw, message):
    with pytest.raises(ValueError, match=message):
        Adjustment.from_dict(raw)


def test_colour_space_helpers_stay_importable_from_adjustments():
    from Imervue.paint import brush_random

    assert brush_random._hsv_to_rgb is adjustments._hsv_to_rgb
    assert brush_random._rgb_to_hsv is adjustments._rgb_to_hsv
    rgb = _grid()[..., :3].astype(np.float32) / 255.0
    np.testing.assert_allclose(adjustments._hsv_to_rgb(adjustments._rgb_to_hsv(rgb)), rgb, atol=1e-5)
    np.testing.assert_allclose(adjustments._hsl_to_rgb(adjustments._rgb_to_hsl(rgb)), rgb, atol=1e-5)
