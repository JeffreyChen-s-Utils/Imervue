"""Tests for scaling 16-bit and floating-point greyscale pictures to 8 bits."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.images.image_loader import decode_image_file
from Imervue.image.high_bit_depth import to_eight_bit


def _grey(img: Image.Image) -> list[int]:
    out = to_eight_bit(img)
    assert out.mode == "L"
    return np.asarray(out)[0].tolist()


def test_sixteen_bit_uses_the_full_range():
    img = Image.fromarray(np.array([[0, 257, 32768, 65535]], dtype=np.uint16))
    assert img.mode == "I;16"
    assert _grey(img) == [0, 1, 128, 255]


def test_big_endian_sixteen_bit_reads_the_same():
    values = np.array([[0, 32768, 65535]], dtype=">u2")
    img = Image.frombytes("I;16B", (3, 1), values.tobytes())
    assert _grey(img) == [0, 128, 255]


def test_thirty_two_bit_within_sixteen_bits_scales_like_sixteen_bit():
    img = Image.fromarray(np.array([[0, 32768, 65535]], dtype=np.int32))
    assert img.mode == "I"
    assert _grey(img) == [0, 128, 255]


@pytest.mark.parametrize("values", [[-100, 0, 100], [0, 100_000, 200_000]])
def test_thirty_two_bit_past_sixteen_bits_is_stretched(values):
    img = Image.fromarray(np.array([values], dtype=np.int32))
    assert _grey(img) == [0, 128, 255]


def test_float_between_zero_and_one_maps_onto_the_byte_range():
    img = Image.fromarray(np.array([[0.0, 0.5, 1.0]], dtype=np.float32))
    assert img.mode == "F"
    assert _grey(img) == [0, 128, 255]


def test_float_outside_zero_to_one_is_stretched():
    img = Image.fromarray(np.array([[-2.0, 3.0, 8.0]], dtype=np.float32))
    assert _grey(img) == [0, 128, 255]


def test_float_nan_and_infinity_show_black():
    img = Image.fromarray(np.array([[np.nan, 0.5, np.inf, -np.inf, 1.0]], dtype=np.float32))
    assert _grey(img) == [0, 128, 0, 0, 255]


def test_float_with_no_finite_value_is_black():
    img = Image.fromarray(np.array([[np.nan, np.inf]], dtype=np.float32))
    assert _grey(img) == [0, 0]


@pytest.mark.parametrize("dtype, value", [(np.float32, 5.0), (np.int32, 100_000)])
def test_a_flat_picture_out_of_range_is_black(dtype, value):
    img = Image.fromarray(np.full((1, 3), value, dtype=dtype))
    assert _grey(img) == [0, 0, 0]


@pytest.mark.parametrize("mode", ["L", "LA", "RGB", "RGBA", "P", "1", "CMYK"])
def test_other_modes_pass_through_untouched(mode):
    img = Image.new(mode, (2, 2))
    assert to_eight_bit(img) is img


def test_info_is_kept():
    img = Image.fromarray(np.zeros((1, 2), dtype=np.uint16))
    img.info["dpi"] = (300, 300)
    assert to_eight_bit(img).info["dpi"] == (300, 300)


@pytest.mark.parametrize("name", ["grey16.png", "grey16.tif"])
@pytest.mark.parametrize("thumbnail", [False, True])
def test_the_viewer_shows_a_sixteen_bit_gradient_as_a_gradient(tmp_path, name, thumbnail):
    path = tmp_path / name
    ramp = np.tile(np.linspace(0, 65535, 256).astype(np.uint16), (8, 1))
    Image.fromarray(ramp).save(path)
    rgba = decode_image_file(str(path), thumbnail=thumbnail)
    row = rgba[0, :, 0].astype(int)
    assert rgba.shape == (8, 256, 4)
    assert row[0] == 0
    assert row[-1] == 255
    assert abs(row[128] - 128) <= 1
    assert np.all(np.diff(row) >= 0)


def test_the_viewer_shows_a_float_tiff_of_zero_to_one(tmp_path):
    path = tmp_path / "depth.tif"
    Image.fromarray(np.tile(np.linspace(0, 1, 64, dtype=np.float32), (4, 1))).save(path)
    row = decode_image_file(str(path))[0, :, 0].astype(int)
    assert row[0] == 0
    assert row[-1] == 255
