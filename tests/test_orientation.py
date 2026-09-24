"""Tests for EXIF orientation transforms."""
from __future__ import annotations

import numpy as np

from Imervue.image.orientation import transform_for_orientation


def _asymmetric(h=2, w=3):
    return np.arange(h * w * 3, dtype=np.uint8).reshape(h, w, 3)


def test_identity():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 1), img)


def test_mirror_horizontal():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 2), img[:, ::-1])


def test_rotate_180():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 3), img[::-1, ::-1])


def test_rotate_90_cw_changes_dimensions():
    img = _asymmetric(2, 3)
    out = transform_for_orientation(img, 6)
    assert out.shape == (3, 2, 3)
    assert np.array_equal(out, np.rot90(img, -1))


def test_rotate_90_ccw():
    img = _asymmetric(2, 3)
    assert np.array_equal(transform_for_orientation(img, 8), np.rot90(img, 1))


def test_transpose_swaps_axes():
    img = _asymmetric(2, 3)
    assert np.array_equal(transform_for_orientation(img, 5), np.swapaxes(img, 0, 1))


def test_unknown_code_is_identity():
    img = _asymmetric()
    assert np.array_equal(transform_for_orientation(img, 99), img)


def test_corrupt_webp_exif_reads_as_upright(tmp_path):
    from test_read_errors import corrupt_exif_webp

    from Imervue.image.orientation import read_orientation

    p = tmp_path / "bad.webp"
    p.write_bytes(corrupt_exif_webp())
    assert read_orientation(str(p)) == 1


import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from Imervue.image.orientation import exif_orientation, transpose_for, upright  # noqa: E402


def _tagged(code, size=(6, 4)):
    img = Image.new("RGB", size)
    exif = Image.Exif()
    exif[0x0112] = code
    img.info["exif"] = exif.tobytes()
    return img


@pytest.mark.parametrize("code", range(1, 9))
def test_pillow_transpose_matches_the_array_transform(code):
    arr = np.random.default_rng(code).integers(0, 255, (3, 5, 4), dtype=np.uint8)
    turned = np.array(transpose_for(Image.fromarray(arr), code))
    assert np.array_equal(turned, transform_for_orientation(arr, code))


@pytest.mark.parametrize("code", [1, 0, 9, -3])
def test_upright_or_unknown_code_returns_the_same_image_without_copying(code):
    img = Image.new("RGB", (6, 4))
    assert transpose_for(img, code) is img


def test_exif_orientation_reads_the_tag_and_defaults_to_upright():
    assert exif_orientation(_tagged(6)) == 6
    assert exif_orientation(Image.new("RGB", (2, 2))) == 1


def test_upright_turns_by_the_images_own_tag():
    assert upright(_tagged(6, size=(6, 4))).size == (4, 6)
    assert upright(_tagged(3, size=(6, 4))).size == (6, 4)


def test_turned_image_no_longer_carries_the_tag(tmp_path):
    """``transpose`` copies ``info``; a second reader would turn the pixels again."""
    exif = Image.Exif()
    exif[0x0112] = 6
    xmp = b'<x:xmpmeta><rdf:Description tiff:Orientation="6"/></x:xmpmeta>'
    path = tmp_path / "p.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif, xmp=xmp)
    with Image.open(path) as img:
        turned = upright(img)
    assert turned.size == (20, 40)
    assert exif_orientation(turned) == 1
    assert b"tiff:Orientation" not in turned.info.get("xmp", b"")
