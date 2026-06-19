"""Tests for the text watermark module."""
from __future__ import annotations

import numpy as np
from PIL import Image

from Imervue.image.watermark import (
    CORNERS,
    WatermarkOptions,
    _clamp,
    _opacity_to_byte,
    _position_for,
    apply_watermark,
)


def _black(h=80, w=120):
    return Image.new("RGBA", (w, h), (0, 0, 0, 255))


def test_is_active():
    assert WatermarkOptions(text="hi").is_active()
    assert not WatermarkOptions(text="   ").is_active()
    assert not WatermarkOptions(text="").is_active()


def test_inactive_returns_same_image():
    img = _black()
    assert apply_watermark(img, WatermarkOptions(text="")) is img


def test_active_watermark_draws_pixels():
    img = _black()
    out = apply_watermark(img, WatermarkOptions(text="X", corner="center", opacity=1.0))
    arr = np.asarray(out)
    assert arr[..., :3].max() > 0   # white text on a black canvas
    assert arr.shape[2] == 4


def test_opacity_to_byte_clamps():
    assert _opacity_to_byte(0.0) == 0
    assert _opacity_to_byte(1.0) == 255
    assert _opacity_to_byte(2.0) == 255
    assert _opacity_to_byte(-1.0) == 0


def test_clamp():
    assert _clamp(5, 0, 10) == 5
    assert _clamp(-1, 0, 10) == 0
    assert _clamp(99, 0, 10) == 10


def test_position_for_corners_stay_in_bounds():
    img_size = (200, 100)
    text_size = (40, 20)
    for corner in CORNERS:
        x, y = _position_for(corner, img_size, text_size, padding=5)
        assert 0 <= x <= img_size[0] - text_size[0]
        assert 0 <= y <= img_size[1] - text_size[1]


def test_position_for_distinguishes_corners():
    left = _position_for("top-left", (200, 100), (40, 20), 5)
    right = _position_for("top-right", (200, 100), (40, 20), 5)
    bottom = _position_for("bottom-left", (200, 100), (40, 20), 5)
    assert right[0] > left[0]      # right corner is further right
    assert bottom[1] > left[1]     # bottom corner is further down
