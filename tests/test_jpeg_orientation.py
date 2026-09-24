"""Tests for the pixel-exact JPEG EXIF orientation rewrite."""
from __future__ import annotations

import io
import struct

import numpy as np
import pytest
from PIL import Image

from Imervue.image.jpeg_orientation import set_jpeg_orientation

_MAKE = 0x010F
_ORIENTATION = 0x0112


def _jpeg(exif: Image.Exif | bytes | None = None) -> bytes:
    arr = np.zeros((8, 16, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)
    buf = io.BytesIO()
    kwargs = {} if exif is None else {"exif": exif}
    Image.fromarray(arr).save(buf, format="JPEG", quality=90, **kwargs)
    return buf.getvalue()


def _pixels(data: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(data)) as img:
        return np.asarray(img)


def _exif_of(data: bytes) -> Image.Exif:
    with Image.open(io.BytesIO(data)) as img:
        return img.getexif()


def _tagged(orientation: int | None = 1) -> Image.Exif:
    exif = Image.Exif()
    exif[_MAKE] = "Canon"
    if orientation is not None:
        exif[_ORIENTATION] = orientation
    exif.get_ifd(0x8769)[0x9003] = "2020:01:02 03:04:05"
    return exif


def _big_endian_exif(orientation: int) -> bytes:
    """An EXIF block in Motorola byte order holding just the orientation."""
    ifd = struct.pack(">H", 1) + struct.pack(">HHIHH", _ORIENTATION, 3, 1, orientation, 0)
    return b"Exif\x00\x00" + b"MM\x00\x2a" + struct.pack(">I", 8) + ifd + struct.pack(">I", 0)


def _differing_bytes(a: bytes, b: bytes) -> int:
    assert len(a) == len(b)
    return sum(x != y for x, y in zip(a, b, strict=True))


def test_existing_tag_is_patched_and_nothing_else_moves():
    before = _jpeg(_tagged(1))
    after = set_jpeg_orientation(before, 6)
    assert _differing_bytes(before, after) == 1        # just the orientation's low byte
    exif = _exif_of(after)
    assert exif[_ORIENTATION] == 6
    assert exif[_MAKE] == "Canon"
    assert exif.get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
    assert np.array_equal(_pixels(after), _pixels(before))


def test_big_endian_tag_is_patched():
    before = _jpeg(_big_endian_exif(3))
    after = set_jpeg_orientation(before, 8)
    assert _differing_bytes(before, after) == 1
    assert _exif_of(after)[_ORIENTATION] == 8


def test_exif_without_the_tag_is_rebuilt_keeping_its_other_tags():
    before = _jpeg(_tagged(None))
    after = set_jpeg_orientation(before, 6)
    exif = _exif_of(after)
    assert exif[_ORIENTATION] == 6
    assert exif[_MAKE] == "Canon"
    assert exif.get_ifd(0x8769)[0x9003] == "2020:01:02 03:04:05"
    assert np.array_equal(_pixels(after), _pixels(before))


def test_tag_stored_with_an_unexpected_type_is_rebuilt():
    ifd = struct.pack("<H", 1) + struct.pack("<HHII", _ORIENTATION, 4, 1, 3)   # LONG, not SHORT
    raw = b"Exif\x00\x00II\x2a\x00" + struct.pack("<I", 8) + ifd + struct.pack("<I", 0)
    after = set_jpeg_orientation(_jpeg(raw), 5)
    assert _exif_of(after)[_ORIENTATION] == 5


def test_jpeg_without_exif_gets_a_segment_after_its_jfif_header():
    before = _jpeg()
    assert before[2:4] == b"\xff\xe0"                  # Pillow writes a JFIF APP0 first
    after = set_jpeg_orientation(before, 8)
    app0_end = 4 + struct.unpack(">H", before[4:6])[0]
    assert after[:app0_end] == before[:app0_end]       # JFIF stays the first segment
    assert after[app0_end:app0_end + 2] == b"\xff\xe1"
    assert _exif_of(after)[_ORIENTATION] == 8
    assert np.array_equal(_pixels(after), _pixels(before))


def test_jpeg_without_any_header_segment_gets_one_after_soi():
    jfif = _jpeg()
    app0_end = 4 + struct.unpack(">H", jfif[4:6])[0]
    bare = jfif[:2] + jfif[app0_end:]
    after = set_jpeg_orientation(bare, 3)
    assert after[2:4] == b"\xff\xe1"
    assert _exif_of(after)[_ORIENTATION] == 3


def test_fill_bytes_before_a_marker_are_skipped():
    data = _jpeg(_tagged(1))
    padded = data[:2] + b"\xff" + data[2:]             # a fill byte before the first marker
    assert _exif_of(set_jpeg_orientation(padded, 6))[_ORIENTATION] == 6


@pytest.mark.parametrize("code", [0, 9, -1])
def test_orientation_outside_1_to_8_is_rejected(code):
    with pytest.raises(ValueError, match="1-8"):
        set_jpeg_orientation(_jpeg(), code)


def test_non_jpeg_is_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="PNG")
    with pytest.raises(ValueError, match="not a JPEG"):
        set_jpeg_orientation(buf.getvalue(), 6)


def test_truncated_segment_is_rejected():
    data = _jpeg()
    with pytest.raises(ValueError, match="truncated"):
        set_jpeg_orientation(data[:10], 6)


def test_jpeg_without_image_data_is_rejected():
    data = _jpeg()
    app0_end = 4 + struct.unpack(">H", data[4:6])[0]
    with pytest.raises(ValueError, match="ends before"):
        set_jpeg_orientation(data[:app0_end], 6)


def test_garbage_between_segments_is_rejected():
    data = _jpeg()
    with pytest.raises(ValueError, match="no JPEG marker"):
        set_jpeg_orientation(data[:2] + b"\x00\x00" + data[2:], 6)


def test_unreadable_exif_block_is_rejected():
    raw = b"Exif\x00\x00XX not a tiff header"
    data = _jpeg()
    segment = b"\xff\xe1" + struct.pack(">H", len(raw) + 2) + raw
    with pytest.raises(ValueError, match="unreadable EXIF"):
        set_jpeg_orientation(data[:2] + segment + data[2:], 6)


def test_exif_that_outgrows_its_segment_is_rejected():
    exif = Image.Exif()
    exif[0x010E] = "x" * 65_490                        # ImageDescription filling the segment
    data = _jpeg(exif)
    with pytest.raises(ValueError, match="too large"):
        set_jpeg_orientation(data, 6)
