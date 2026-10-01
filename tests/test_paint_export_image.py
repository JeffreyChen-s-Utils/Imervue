"""Paint's Export image…: the format follows the file type the user picks.

It wrote PNG whatever name was typed. Qt-free apart from the stand-in
workspace, so this file runs on headless CI.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from Imervue.paint import file_menu as mod
from Imervue.paint.file_menu import _FileMenuBridge, export_format_for, write_export_image


@pytest.mark.parametrize(("path", "expected"), [
    ("C:/art/a.png", ("png", "C:/art/a.png")),
    ("C:/art/a.JPG", ("jpeg", "C:/art/a.JPG")),
    ("C:/art/a.jpeg", ("jpeg", "C:/art/a.jpeg")),
    ("C:/art/a.webp", ("webp", "C:/art/a.webp")),
    ("C:/art/a.tif", ("tiff", "C:/art/a.tif")),
    ("C:/art/a.tiff", ("tiff", "C:/art/a.tiff")),
    ("C:/art/a.bmp", ("bmp", "C:/art/a.bmp")),
    ("C:/art/a", ("png", "C:/art/a.png")),
    ("C:/art/a.gif", ("png", "C:/art/a.gif.png")),
])
def test_export_format_for(path, expected):
    assert export_format_for(path) == expected


def _composite():
    image = np.zeros((16, 24, 4), dtype=np.uint8)
    image[..., 0] = 200
    image[..., 3] = 255
    image[:8, :8, 3] = 0   # a transparent block (JPEG blurs a single pixel)
    return image


@pytest.mark.parametrize(("suffix", "pil_format", "mode"), [
    (".png", "PNG", "RGBA"),
    (".jpg", "JPEG", "RGB"),
    (".webp", "WEBP", "RGBA"),
    (".tiff", "TIFF", "RGBA"),
    (".bmp", "BMP", "RGB"),
])
def test_each_format_is_written_full_size(tmp_path, suffix, pil_format, mode):
    fmt, path = export_format_for(str(tmp_path / f"out{suffix}"))
    write_export_image(_composite(), path, fmt)
    with Image.open(path) as done:
        assert done.format == pil_format
        assert done.size == (24, 16)
        assert done.mode == mode


@pytest.mark.parametrize("suffix", [".jpg", ".bmp"])
def test_formats_without_alpha_are_flattened_onto_white(tmp_path, suffix):
    """A 32-bit BMP reads back as RGB, so a transparent pixel showed its hidden red."""
    fmt, path = export_format_for(str(tmp_path / f"out{suffix}"))
    write_export_image(_composite(), path, fmt)
    with Image.open(path) as done:
        assert min(done.getpixel((2, 2))) > 240
        assert done.getpixel((20, 12))[0] > 180


def _bridge(tmp_path, picked, toasts, cleaned=None):
    cleaned = [] if cleaned is None else cleaned
    workspace = SimpleNamespace(
        canvas=lambda: SimpleNamespace(document=lambda: SimpleNamespace(composite=_composite)),
        toast=SimpleNamespace(success=toasts.append, warning=toasts.append, error=toasts.append),
        mark_active_tab_clean=lambda: cleaned.append(True),
    )
    bridge = _FileMenuBridge(workspace)
    bridge._pick_save_file = lambda **_kw: picked  # noqa: SLF001
    return bridge


def test_export_writes_the_picked_type(tmp_path):
    toasts, cleaned = [], []
    target = tmp_path / "picture.webp"
    _bridge(tmp_path, str(target), toasts, cleaned).export_active_image()
    with Image.open(target) as done:
        assert done.format == "WEBP"
    assert toasts
    assert cleaned == []   # a flattened export is not a save of the layers


def test_export_without_a_suffix_writes_png(tmp_path):
    toasts = []
    _bridge(tmp_path, str(tmp_path / "picture"), toasts).export_active_image()
    with Image.open(tmp_path / "picture.png") as done:
        assert done.format == "PNG"


def test_a_cancelled_dialog_writes_nothing(tmp_path):
    toasts = []
    _bridge(tmp_path, None, toasts).export_active_image()
    assert list(tmp_path.iterdir()) == []
    assert toasts == []


def test_the_dialog_offers_every_type():
    for name in ("PNG", "JPEG", "WebP", "TIFF", "BMP"):
        assert name in mod.EXPORT_IMAGE_FILTER
