"""Tests for rewriting a WebP's EXIF chunk without re-encoding the image."""
from __future__ import annotations

import io
import struct

import numpy as np
import pytest
from PIL import Image, ImageCms

from Imervue.image.webp_exif import update_webp_exif

_MAKE = 0x010F
_DATE = "2020:01:02 03:04:05"


def _webp(alpha: bool = False, **kwargs) -> bytes:
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, (21, 37, 4 if alpha else 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "WEBP", **kwargs)
    return buf.getvalue()


def _animated() -> bytes:
    frames = [Image.new("RGB", (10, 8), c) for c in ((255, 0, 0), (0, 255, 0))]
    buf = io.BytesIO()
    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=50)
    return buf.getvalue()


def _chunk_ids(data: bytes) -> list[bytes]:
    ids, pos = [], 12
    while pos + 8 <= len(data):
        (size,) = struct.unpack("<I", data[pos + 4:pos + 8])
        ids.append(data[pos:pos + 4])
        pos += 8 + size + (size & 1)
    return ids


def _tag(exif):
    exif[_MAKE] = "Canon"
    exif.get_ifd(0x8769)[0x9003] = _DATE
    exif[0x8769] = 0


def _frames(data: bytes) -> list[bytes]:
    with Image.open(io.BytesIO(data)) as img:
        out = []
        for index in range(getattr(img, "n_frames", 1)):
            img.seek(index)
            out.append(img.convert("RGBA").tobytes())
    return out


def _icc() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


@pytest.mark.parametrize("source", [
    pytest.param(lambda: _webp(quality=80), id="simple-lossy"),
    pytest.param(lambda: _webp(lossless=True), id="simple-lossless"),
    pytest.param(lambda: _webp(alpha=True, lossless=True), id="lossless-alpha"),
    pytest.param(lambda: _webp(alpha=True, quality=80), id="lossy-alpha"),
    pytest.param(lambda: _webp(quality=80, icc_profile=_icc()), id="extended-icc"),
    pytest.param(_animated, id="animated"),
])
def test_exif_is_written_and_the_image_data_is_untouched(source):
    before = source()
    after = update_webp_exif(before, _tag)
    assert _frames(after) == _frames(before)
    with Image.open(io.BytesIO(after)) as img:
        assert img.getexif()[_MAKE] == "Canon"
        assert img.getexif().get_ifd(0x8769)[0x9003] == _DATE
        with Image.open(io.BytesIO(before)) as original:
            assert img.size == original.size
            assert img.mode == original.mode
            assert img.info.get("icc_profile") == original.info.get("icc_profile")
    assert after[4:8] == struct.pack("<I", len(after) - 8)          # RIFF size
    flags = after[20]
    assert _chunk_ids(after)[0] == b"VP8X" and flags & 0x08          # EXIF flag set


def test_simple_file_is_promoted_with_its_canvas_and_alpha_flag():
    before = _webp(alpha=True, lossless=True)
    assert _chunk_ids(before) == [b"VP8L"]
    after = update_webp_exif(before, _tag)
    assert _chunk_ids(after) == [b"VP8X", b"VP8L", b"EXIF"]
    vp8x = after[20:30]
    assert vp8x[0] == 0x08 | 0x10                                     # EXIF + alpha
    width = int.from_bytes(vp8x[4:7], "little") + 1
    height = int.from_bytes(vp8x[7:10], "little") + 1
    assert (width, height) == (37, 21)


def test_existing_exif_is_replaced_not_duplicated():
    old = Image.Exif()
    old[_MAKE] = "Old"
    after = update_webp_exif(_webp(quality=80, exif=old), _tag)
    assert _chunk_ids(after).count(b"EXIF") == 1
    with Image.open(io.BytesIO(after)) as img:
        assert img.getexif()[_MAKE] == "Canon"


def test_exif_goes_before_an_xmp_chunk():
    before = _webp(quality=80, xmp=b"<x:xmpmeta/>")
    assert _chunk_ids(before)[-1] == b"XMP "
    after = update_webp_exif(before, _tag)
    ids = _chunk_ids(after)
    assert ids.index(b"EXIF") == ids.index(b"XMP ") - 1


def test_chunk_stored_with_the_exif_header_is_read():
    """Some writers keep the JPEG-style Exif\\0\\0 prefix inside the chunk."""
    data = update_webp_exif(_webp(quality=80), _tag)
    pos = data.index(b"EXIF")
    size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
    body = b"Exif\x00\x00" + data[pos + 8:pos + 8 + size]
    prefixed = data[:pos] + b"EXIF" + struct.pack("<I", len(body)) + body
    prefixed = prefixed[:4] + struct.pack("<I", len(prefixed) - 8) + prefixed[8:]

    def keep(exif):
        assert exif[_MAKE] == "Canon"
        exif[0x0131] = "Imervue"

    after = update_webp_exif(prefixed, keep)
    with Image.open(io.BytesIO(after)) as img:
        assert img.getexif()[0x0131] == "Imervue"


@pytest.mark.parametrize(("data", "message"), [
    (b"\xff\xd8\xff", "not a WebP"),
    (b"RIFF\x04\x00\x00\x00WEBP", "without chunks"),
    (b"RIFF\x20\x00\x00\x00WEBPVP8 \xff\x00\x00\x00abc", "truncated"),
    (b"RIFF\x12\x00\x00\x00WEBPVP8 \x06\x00\x00\x00abcdef", "unrecognised"),
])
def test_malformed_webp_is_rejected(data, message):
    with pytest.raises(ValueError, match=message):
        update_webp_exif(data, _tag)
