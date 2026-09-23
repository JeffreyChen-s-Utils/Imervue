"""``IMAGE_READ_ERRORS`` must cover whatever Pillow raises for a bad image file."""
from __future__ import annotations

import contextlib
import io
import random
import warnings

import pytest
from PIL import Image

from Imervue.image.read_errors import IMAGE_READ_ERRORS

_FORMATS = ["PNG", "JPEG", "GIF", "TIFF", "WEBP", "BMP", "ICO"]


def _encoded(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.linear_gradient("L").convert("RGB").resize((32, 32)).save(buf, fmt)
    return buf.getvalue()


def _decode(data: bytes) -> None:
    with Image.open(io.BytesIO(data)) as img:
        img.thumbnail((16, 16))
        img.convert("RGBA").tobytes()


@pytest.mark.parametrize("fmt", _FORMATS)
def test_corrupt_files_raise_only_read_errors(fmt):
    rng = random.Random(fmt)
    good = _encoded(fmt)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(150):
            data = bytearray(good)
            for _flip in range(rng.randint(1, 6)):
                data[rng.randrange(len(data))] = rng.randrange(256)
            if rng.random() < 0.3:
                data = data[:rng.randrange(len(data))]
            with contextlib.suppress(IMAGE_READ_ERRORS):
                _decode(bytes(data))


def test_missing_and_non_image_files(tmp_path):
    text = tmp_path / "notes.txt"
    text.write_text("not an image", encoding="utf-8")
    for path in (tmp_path / "absent.png", text, tmp_path):
        with pytest.raises(IMAGE_READ_ERRORS):
            Image.open(path)


def test_decompression_bomb_is_covered(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(IMAGE_READ_ERRORS):
        _decode(_encoded("PNG"))
