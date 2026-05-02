"""Tests for the auto colour-separation engine."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.divide_layer import (
    DEFAULT_QUANTIZE,
    MAX_DIVIDE_BUCKETS,
    QUANTIZE_MAX,
    QUANTIZE_MIN,
    ColorLayer,
    divide_layer_into_color_layers,
    render_color_layer,
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_non_rgba():
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(np.zeros((4, 4, 3), dtype=np.uint8))


def test_rejects_non_uint8():
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(np.zeros((4, 4, 4), dtype=np.float32))


def test_rejects_quantize_below_min():
    canvas = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(canvas, quantize=QUANTIZE_MIN - 1)


def test_rejects_quantize_above_max():
    canvas = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(canvas, quantize=QUANTIZE_MAX + 1)


def test_rejects_zero_max_buckets():
    canvas = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(canvas, max_buckets=0)


def test_rejects_alpha_threshold_out_of_range():
    canvas = np.full((4, 4, 4), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        divide_layer_into_color_layers(canvas, alpha_threshold=300)


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_fully_transparent_layer_yields_no_buckets():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    assert divide_layer_into_color_layers(canvas) == []


def test_single_flat_colour_produces_one_layer():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., :3] = (200, 50, 50)
    canvas[..., 3] = 255
    layers = divide_layer_into_color_layers(canvas)
    assert len(layers) == 1
    assert layers[0].color == (200, 50, 50)
    assert layers[0].pixel_count == 16
    assert layers[0].mask.all()


# ---------------------------------------------------------------------------
# Multiple colours — bucket grouping + sort order
# ---------------------------------------------------------------------------


def test_two_colours_produce_two_layers():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[:, :2, :3] = (255, 0, 0)   # red half
    canvas[:, 2:, :3] = (0, 255, 0)   # green half
    layers = divide_layer_into_color_layers(canvas)
    assert len(layers) == 2
    # Colours are returned with both expected RGBs (order is by area;
    # in this case they tie, so accept either ordering).
    found = {layer.color for layer in layers}
    assert found == {(255, 0, 0), (0, 255, 0)}


def test_layers_sorted_by_pixel_count_descending():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[:, :3, :3] = (255, 0, 0)   # red 4x3 = 12 pixels
    canvas[:, 3:, :3] = (0, 0, 255)   # blue 4x1 = 4 pixels
    layers = divide_layer_into_color_layers(canvas)
    assert layers[0].color == (255, 0, 0)
    assert layers[0].pixel_count > layers[1].pixel_count


def test_quantization_groups_near_duplicates():
    """Two RGB tuples one quantize-step apart land in the same bucket."""
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[:2, :, :3] = (200, 0, 0)
    canvas[2:, :, :3] = (203, 0, 0)   # within the default quantize=16 bucket
    layers = divide_layer_into_color_layers(canvas, quantize=16)
    assert len(layers) == 1


def test_finer_quantization_separates_them():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[:2, :, :3] = (200, 0, 0)
    canvas[2:, :, :3] = (203, 0, 0)
    layers = divide_layer_into_color_layers(canvas, quantize=1)
    assert len(layers) == 2


def test_max_buckets_caps_output():
    canvas = np.zeros((1, 8, 4), dtype=np.uint8)
    canvas[..., 3] = 255
    canvas[0, :, 0] = np.arange(0, 256, 32, dtype=np.uint8)   # 8 distinct
    layers = divide_layer_into_color_layers(canvas, max_buckets=3, quantize=1)
    assert len(layers) == 3


def test_alpha_threshold_drops_translucent_pixels():
    canvas = np.zeros((4, 4, 4), dtype=np.uint8)
    canvas[:2, :, :3] = (255, 0, 0)
    canvas[:2, :, 3] = 255
    canvas[2:, :, :3] = (0, 255, 0)
    canvas[2:, :, 3] = 50    # below threshold → ignored
    layers = divide_layer_into_color_layers(canvas, alpha_threshold=128)
    assert len(layers) == 1
    assert layers[0].color == (255, 0, 0)


# ---------------------------------------------------------------------------
# render_color_layer
# ---------------------------------------------------------------------------


def test_render_color_layer_paints_inside_mask():
    mask = np.zeros((4, 4), dtype=np.bool_)
    mask[:2, :] = True
    cl = ColorLayer(color=(10, 200, 50), mask=mask, pixel_count=8)
    img = render_color_layer((4, 4), cl)
    assert (img[:2, :, 3] == 255).all()
    assert (img[2:, :, 3] == 0).all()
    assert tuple(img[0, 0, :3]) == (10, 200, 50)


def test_render_color_layer_rejects_shape_mismatch():
    mask = np.zeros((4, 4), dtype=np.bool_)
    cl = ColorLayer(color=(0, 0, 0), mask=mask, pixel_count=0)
    with pytest.raises(ValueError):
        render_color_layer((8, 8), cl)


# ---------------------------------------------------------------------------
# Defaults sanity
# ---------------------------------------------------------------------------


def test_default_quantize_is_within_bounds():
    assert QUANTIZE_MIN <= DEFAULT_QUANTIZE <= QUANTIZE_MAX


def test_default_max_buckets_is_positive():
    assert MAX_DIVIDE_BUCKETS > 0
