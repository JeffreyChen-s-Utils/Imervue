"""Tests for the Pillow-only JPEG EXIF segment rewrite."""
from __future__ import annotations

import io
import struct

import numpy as np
import pytest
from PIL import Image

from _exif_samples import payload_with_thumbnail, thumbnail_jpeg, thumbnail_of

from Imervue.image.jpeg_exif import (
    exif_segment, load_exif, replace_exif_segment, serialize_exif, update_jpeg_exif,
)

_MAKE = 0x010F


def _jpeg(exif: bytes | Image.Exif | None = None) -> bytes:
    arr = np.zeros((8, 16, 3), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", **({} if exif is None else {"exif": exif}))
    return buf.getvalue()


def _scan(data: bytes) -> bytes:
    return data[data.index(b"\xff\xda"):]


@pytest.mark.parametrize("order", ["<", ">"])
def test_update_keeps_the_thumbnail_and_the_pixels(order):
    """Pillow's Exif.tobytes drops IFD1, the thumbnail other programs show first."""
    original = _jpeg(payload_with_thumbnail(order))
    assert thumbnail_of(original) == thumbnail_jpeg()

    def tag(exif):
        exif[0x0131] = "Imervue"

    updated = update_jpeg_exif(original, tag)
    assert thumbnail_of(updated) == thumbnail_jpeg()
    assert _scan(updated) == _scan(original)
    with Image.open(io.BytesIO(updated)) as img:
        assert img.getexif()[_MAKE] == "Canon"
        assert img.getexif()[0x0131] == "Imervue"


def test_update_of_a_jpeg_without_exif_adds_a_segment_after_jfif():
    original = _jpeg()
    assert exif_segment(original) is None

    def tag(exif):
        exif[_MAKE] = "Nikon"

    updated = update_jpeg_exif(original, tag)
    app0_end = 4 + struct.unpack(">H", original[4:6])[0]
    assert updated[:app0_end] == original[:app0_end]
    assert updated[app0_end:app0_end + 2] == b"\xff\xe1"
    assert _scan(updated) == _scan(original)
    with Image.open(io.BytesIO(updated)) as img:
        assert img.getexif()[_MAKE] == "Nikon"


def test_serialize_without_an_original_is_plain_pillow():
    exif = Image.Exif()
    exif[_MAKE] = "Sony"
    assert serialize_exif(exif) == exif.tobytes()
    no_ifd1 = b"Exif\x00\x00II*\x00\x08\x00\x00\x00" + b"\x00\x00" + b"\x00\x00\x00\x00"
    assert serialize_exif(exif, no_ifd1) == exif.tobytes()


@pytest.mark.filterwarnings("ignore:Corrupt EXIF data:UserWarning")
def test_a_thumbnail_pointing_outside_the_block_is_not_copied():
    payload = bytearray(payload_with_thumbnail())
    payload[-1] = 0x00                               # the "JPEG" no longer ends as one…
    broken = bytes(payload[:-200])                   # …and is cut short
    exif = load_exif(broken)
    assert serialize_exif(exif, broken) == exif.tobytes()


def test_replace_swaps_only_the_exif_segment():
    original = _jpeg(Image.Exif())
    payload = b"Exif\x00\x00" + Image.Exif().tobytes()[6:]
    replaced = replace_exif_segment(original, payload)
    assert _scan(replaced) == _scan(original)


def test_oversized_payload_is_rejected():
    with pytest.raises(ValueError, match="too large"):
        replace_exif_segment(_jpeg(), b"Exif\x00\x00" + b"\x00" * 65_530)


@pytest.mark.parametrize(("data", "message"), [
    (b"\x89PNG\r\n", "not a JPEG"),
    (b"\xff\xd8\xff\xe1\x00", "ends before"),
    (b"\xff\xd8\xff\xe1\x00\x40abc", "truncated"),
    (b"\xff\xd8\x00\x00\xff\xda", "no JPEG marker"),
])
def test_malformed_data_is_rejected(data, message):
    with pytest.raises(ValueError, match=message):
        update_jpeg_exif(data, lambda _exif: None)


def test_unreadable_exif_block_is_rejected():
    raw = b"Exif\x00\x00XX not a tiff header"
    data = _jpeg()
    segment = b"\xff\xe1" + struct.pack(">H", len(raw) + 2) + raw
    with pytest.raises(ValueError, match="unreadable EXIF"):
        update_jpeg_exif(data[:2] + segment + data[2:], lambda _exif: None)
