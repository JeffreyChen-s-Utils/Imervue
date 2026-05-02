"""Tests for the 1-bit binary ink layer engine + per-layer hint."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.binary_layer import (
    BINARY_SOURCE_ALPHA,
    BINARY_SOURCE_LUMA,
    BINARY_SOURCES,
    BINARY_THRESHOLD_MAX,
    BINARY_THRESHOLD_MIN,
    DEFAULT_BINARY_THRESHOLD,
    BinarySettings,
    render_binary_layer,
)


# ---------------------------------------------------------------------------
# BinarySettings — validation
# ---------------------------------------------------------------------------


def test_binary_defaults_pass_validation():
    settings = BinarySettings()
    assert settings.threshold == DEFAULT_BINARY_THRESHOLD
    assert settings.color == (0, 0, 0)
    assert settings.source == BINARY_SOURCE_ALPHA


def test_binary_rejects_threshold_below_min():
    with pytest.raises(ValueError):
        BinarySettings(threshold=BINARY_THRESHOLD_MIN - 1)


def test_binary_rejects_threshold_above_max():
    with pytest.raises(ValueError):
        BinarySettings(threshold=BINARY_THRESHOLD_MAX + 1)


def test_binary_rejects_color_with_wrong_length():
    with pytest.raises(ValueError):
        BinarySettings(color=(0, 0))   # type: ignore[arg-type]


def test_binary_rejects_color_component_out_of_range():
    with pytest.raises(ValueError):
        BinarySettings(color=(0, 0, 256))


def test_binary_rejects_unknown_source():
    with pytest.raises(ValueError):
        BinarySettings(source="rgb")


def test_binary_accepts_each_documented_source():
    for source in BINARY_SOURCES:
        BinarySettings(source=source)


# ---------------------------------------------------------------------------
# BinarySettings — to_dict / from_dict round-trip
# ---------------------------------------------------------------------------


def test_binary_to_from_dict_round_trips():
    original = BinarySettings(
        threshold=200, color=(40, 80, 200), source=BINARY_SOURCE_LUMA,
    )
    rebuilt = BinarySettings.from_dict(original.to_dict())
    assert rebuilt == original


def test_binary_from_dict_returns_none_for_garbage():
    assert BinarySettings.from_dict(None) is None
    assert BinarySettings.from_dict({"threshold": "nope"}) is None
    assert BinarySettings.from_dict({"color": [0, 0]}) is None


# ---------------------------------------------------------------------------
# render_binary_layer — alpha threshold
# ---------------------------------------------------------------------------


def test_render_alpha_above_threshold_becomes_full_ink():
    layer = np.zeros((4, 4, 4), dtype=np.uint8)
    layer[:, :2, 3] = 200    # half the canvas is high-alpha
    layer[:, 2:, 3] = 50     # other half is below the default 128 threshold
    out = render_binary_layer(layer, BinarySettings())
    # The high-alpha half is fully opaque ink; the low-alpha half is
    # fully transparent.
    assert (out[:, :2, 3] == 255).all()
    assert (out[:, 2:, 3] == 0).all()


def test_render_alpha_uses_tone_color():
    layer = np.zeros((2, 2, 4), dtype=np.uint8)
    layer[..., 3] = 255
    out = render_binary_layer(layer, BinarySettings(color=(10, 20, 200)))
    inked = out[out[..., 3] > 0]
    assert inked.size > 0
    assert (inked[:, 0] == 10).all()
    assert (inked[:, 1] == 20).all()
    assert (inked[:, 2] == 200).all()


def test_render_alpha_threshold_inclusive_check_is_strict():
    """A pixel exactly at the threshold is NOT ink — strict greater-than."""
    layer = np.zeros((1, 1, 4), dtype=np.uint8)
    layer[..., 3] = 128
    out = render_binary_layer(layer, BinarySettings(threshold=128))
    assert out[0, 0, 3] == 0


def test_render_zero_alpha_input_yields_empty_output():
    layer = np.zeros((3, 3, 4), dtype=np.uint8)
    out = render_binary_layer(layer, BinarySettings())
    assert (out[..., 3] == 0).all()


# ---------------------------------------------------------------------------
# render_binary_layer — luma threshold
# ---------------------------------------------------------------------------


def test_render_luma_inks_dark_pixels():
    """Dark RGB on opaque pixels becomes ink under the luma source."""
    layer = np.zeros((2, 2, 4), dtype=np.uint8)
    layer[..., 3] = 255
    layer[..., :3] = 30   # very dark grey
    out = render_binary_layer(
        layer, BinarySettings(threshold=128, source=BINARY_SOURCE_LUMA),
    )
    assert (out[..., 3] == 255).all()


def test_render_luma_skips_light_pixels():
    layer = np.full((2, 2, 4), 255, dtype=np.uint8)
    out = render_binary_layer(
        layer, BinarySettings(threshold=128, source=BINARY_SOURCE_LUMA),
    )
    assert (out[..., 3] == 0).all()


def test_render_luma_ignores_transparent_pixels():
    """Transparent pixels with black RGB must not paint as ink."""
    layer = np.zeros((2, 2, 4), dtype=np.uint8)
    # alpha = 0, RGB = 0 — luma reads black, but alpha == 0 means
    # there's no actual stroke painted there.
    out = render_binary_layer(
        layer, BinarySettings(threshold=128, source=BINARY_SOURCE_LUMA),
    )
    assert (out[..., 3] == 0).all()


# ---------------------------------------------------------------------------
# render_binary_layer — input shape
# ---------------------------------------------------------------------------


def test_render_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        render_binary_layer(bad, BinarySettings())


def test_render_rejects_non_uint8():
    bad = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        render_binary_layer(bad, BinarySettings())


def test_render_does_not_mutate_input():
    layer = np.zeros((4, 4, 4), dtype=np.uint8)
    layer[..., 3] = 200
    snapshot = layer.copy()
    render_binary_layer(layer, BinarySettings())
    np.testing.assert_array_equal(layer, snapshot)
