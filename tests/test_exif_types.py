"""Tests for putting back the EXIF entry types Pillow's serialiser gets wrong."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from _exif_samples import exif_block, rational_bytes

from Imervue.image.exif_types import entry_types, restore_types

_UNDEFINED, _BYTE, _RATIONAL, _SRATIONAL = 7, 1, 5, 10


@pytest.mark.parametrize("order", ["<", ">"])
def test_spec_types_are_put_back(order):
    wrong = exif_block(order, [
        (0x9286, _BYTE, b"ASCII\0\0\0hi"),                 # UserComment
        (0x9204, _RATIONAL, rational_bytes(order, 1, 3)),        # ExposureBiasValue
        (0x927C, _BYTE, b"maker-note-bytes"),               # MakerNote
    ])
    fixed = restore_types(wrong)
    types = entry_types(fixed)
    assert types[("exif", 0x9286)] == _UNDEFINED
    assert types[("exif", 0x9204)] == _SRATIONAL
    assert types[("exif", 0x927C)] == _UNDEFINED
    assert len(fixed) == len(wrong)
    changed = [i for i, (a, b) in enumerate(zip(fixed, wrong, strict=True)) if a != b]
    assert len(changed) == 3                                  # one type byte per entry


def test_original_types_cover_vendor_tags():
    original = exif_block("<", [], [(0xC4B0, _UNDEFINED, b"vendor-blob")])
    wrong = exif_block("<", [], [(0xC4B0, _BYTE, b"vendor-blob")])
    assert entry_types(restore_types(wrong, original))[("0th", 0xC4B0)] == _UNDEFINED


def test_spec_wins_over_an_original_that_was_already_wrong():
    already_wrong = exif_block("<", [(0x9286, _BYTE, b"ASCII\0\0\0hi")])
    assert entry_types(restore_types(already_wrong, already_wrong))[("exif", 0x9286)] == _UNDEFINED


def test_types_of_another_size_are_left_alone():
    """ASCII ↔ UNDEFINED share a size, but a 1-byte BYTE can't become an 8-byte SRATIONAL."""
    wrong = exif_block("<", [(0x9204, _BYTE, b"\x01\x02\x03\x04\x05\x06\x07\x08")])
    assert entry_types(restore_types(wrong))[("exif", 0x9204)] == _BYTE


@pytest.mark.parametrize("payload", [b"", b"not exif", b"Exif\x00\x00XX", b"Exif\x00\x00II*\x00"])
def test_unparseable_payloads_pass_through(payload):
    assert restore_types(payload) == payload
    assert entry_types(payload) == {}


def test_truncated_ifd_is_returned_unchanged():
    block = exif_block("<", [(0x9286, _BYTE, b"ASCII\0\0\0hi")])
    cut = block[:30]
    assert restore_types(cut) == cut


def test_pillow_round_trip_keeps_the_camera_types():
    """End to end: a Pillow re-serialisation restored against the camera's own block."""
    original = exif_block(">", [
        (0x9286, _UNDEFINED, b"ASCII\0\0\0hi"),
        (0x9204, _SRATIONAL, rational_bytes(">", 0, 1)),
        (0xA300, _UNDEFINED, b"\x03"),
    ])
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "JPEG", exif=original)
    with Image.open(io.BytesIO(buf.getvalue())) as img:
        reserialised = img.getexif().tobytes()
    assert entry_types(reserialised)[("exif", 0x9286)] == _BYTE        # Pillow's guess
    fixed = entry_types(restore_types(reserialised, original))
    assert fixed[("exif", 0x9286)] == _UNDEFINED
    assert fixed[("exif", 0x9204)] == _SRATIONAL
    assert fixed[("exif", 0xA300)] == _UNDEFINED
