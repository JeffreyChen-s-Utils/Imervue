"""Tests for the Pillow settings the entry points apply: giant pictures and files cut short."""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageFile

from Imervue.gpu_image_view.images.image_loader import decode_image_file
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.system import pixel_limit
from Imervue.system.pillow_setup import configure_pillow

_HEIGHT, _WIDTH = 240, 320


@pytest.fixture
def configured(monkeypatch):
    """Apply :func:`configure_pillow`, restoring Pillow's defaults afterwards."""
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", ImageFile.LOAD_TRUNCATED_IMAGES)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", Image.MAX_IMAGE_PIXELS)
    configure_pillow()


def _noise() -> np.ndarray:
    return (np.random.default_rng(7).random((_HEIGHT, _WIDTH, 3)) * 255).astype(np.uint8)


def _write(tmp_path, name: str, fmt: str, keep: float) -> tuple[str, str]:
    """A whole file and a copy cut after *keep* of its bytes, as ``(whole, cut)`` paths."""
    buf = io.BytesIO()
    Image.fromarray(_noise()).save(buf, fmt)
    data = buf.getvalue()
    whole, cut = tmp_path / f"whole_{name}", tmp_path / f"cut_{name}"
    whole.write_bytes(data)
    cut.write_bytes(data[: int(len(data) * keep)])
    return str(whole), str(cut)


def test_configure_pillow_reads_files_cut_short_and_raises_the_pixel_limit(monkeypatch):
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", False)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", Image.MAX_IMAGE_PIXELS)
    monkeypatch.setattr(pixel_limit, "total_memory_bytes", lambda: 48 * 1024 ** 3)
    configure_pillow()
    assert ImageFile.LOAD_TRUNCATED_IMAGES is True
    assert Image.MAX_IMAGE_PIXELS == 48 * 1024 ** 3 // 24


def test_pillows_default_refuses_a_file_cut_short(tmp_path):
    _whole, cut = _write(tmp_path, "a.jpg", "JPEG", 0.6)
    with pytest.raises(OSError, match="truncated"):
        decode_image_file(cut)


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize("thumbnail", [False, True])
def test_a_jpeg_cut_short_shows_what_was_read_and_grey_below(tmp_path, thumbnail):
    whole, cut = _write(tmp_path, "a.jpg", "JPEG", 0.6)
    full, partial = decode_image_file(whole, thumbnail=thumbnail), decode_image_file(cut, thumbnail=thumbnail)
    assert partial.shape == full.shape == (_HEIGHT, _WIDTH, 4)
    assert np.array_equal(partial[:16], full[:16])
    assert np.all(partial[-1, :, :3] == 128)


@pytest.mark.usefixtures("configured")
def test_a_png_cut_short_shows_what_was_read_and_black_below(tmp_path):
    whole, cut = _write(tmp_path, "a.png", "PNG", 0.6)
    full, partial = decode_image_file(whole), decode_image_file(cut)
    assert partial.shape == full.shape
    assert np.array_equal(partial[:16], full[:16])
    assert np.all(partial[-1, :, :3] == 0)


@pytest.mark.usefixtures("configured")
def test_a_file_cut_before_its_size_is_known_still_fails(tmp_path):
    cut = tmp_path / "cut.jpg"
    cut.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JF")   # the file ends inside its first header
    with pytest.raises(IMAGE_READ_ERRORS):
        decode_image_file(str(cut))
