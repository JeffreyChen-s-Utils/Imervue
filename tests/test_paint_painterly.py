"""Tests for the stroke-based oil painting renderer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.painterly import PainterlyOptions, paint

SMALL = PainterlyOptions(radii=(4, 2), max_length=4, seed=3)


def _split(size: int = 48) -> np.ndarray:
    """Left half dark red, right half pale blue."""
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, : size // 2] = (120, 20, 20)
    image[:, size // 2:] = (150, 180, 220)
    return image


def test_the_painting_has_the_image_size_and_no_alpha():
    out = paint(_split(), SMALL)
    assert out.shape == (48, 48, 3)
    assert out.dtype == np.uint8


def test_an_alpha_channel_is_accepted_and_dropped():
    image = np.dstack([_split(), np.full((48, 48), 255, np.uint8)])
    assert paint(image, SMALL).shape == (48, 48, 3)


def test_the_same_seed_paints_the_same_picture():
    assert np.array_equal(paint(_split(), SMALL), paint(_split(), SMALL))


def test_a_flat_image_is_painted_in_its_own_colour():
    flat = np.full((40, 40, 3), (90, 140, 60), dtype=np.uint8)
    out = paint(flat, PainterlyOptions(radii=(4, 2), max_length=4, impasto=0.0, bristle=0.0)).astype(int)
    assert np.abs(out - (90, 140, 60)).max() <= 3


def test_each_half_keeps_its_colour():
    out = paint(_split(), SMALL).astype(float)
    left, right = out[:, 4:18].mean(axis=(0, 1)), out[:, 30:44].mean(axis=(0, 1))
    assert left[0] > left[2] + 40               # still red
    assert right[2] > right[0] + 30             # still blue


def test_without_bristles_or_impasto_the_canvas_is_only_strokes():
    plain = PainterlyOptions(radii=(4, 2), max_length=4, impasto=0.0, bristle=0.0, seed=3)
    textured = PainterlyOptions(radii=(4, 2), max_length=4, impasto=0.5, bristle=0.2, seed=3)
    assert not np.array_equal(paint(_split(), plain), paint(_split(), textured))


def test_importance_brings_fine_strokes_where_it_is_high():
    image = np.zeros((48, 48, 3), dtype=np.uint8)
    image[::3, :] = 200                          # fine stripes everywhere
    coarse = PainterlyOptions(radii=(6, 2), threshold=60.0, max_length=4, impasto=0.0, bristle=0.0, seed=1)
    weight = np.zeros((48, 48), dtype=np.float32)
    weight[:, 24:] = 1.0
    out = paint(image, coarse, importance=weight).astype(float)
    detail = lambda block: np.abs(np.diff(block, axis=0)).mean()  # noqa: E731
    assert detail(out[:, 28:44]) > detail(out[:, 4:20])


@pytest.mark.parametrize("image", [np.zeros((10, 10), np.uint8), np.zeros((10, 10, 3), np.float32),
                                   np.zeros((1, 10, 3), np.uint8)])
def test_a_wrong_image_is_refused(image):
    with pytest.raises(ValueError):
        paint(image, SMALL)


@pytest.mark.parametrize("options", [PainterlyOptions(radii=()), PainterlyOptions(radii=(2, 4)),
                                     PainterlyOptions(radii=(4, 0)), PainterlyOptions(threshold=0.0),
                                     PainterlyOptions(curvature=1.5)])
def test_wrong_options_are_refused(options):
    with pytest.raises(ValueError):
        paint(_split(), options)


def test_an_importance_of_the_wrong_shape_is_refused():
    with pytest.raises(ValueError):
        paint(_split(), SMALL, importance=np.ones((10, 10), np.float32))
