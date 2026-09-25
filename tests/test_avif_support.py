"""AVIF is read and written by Pillow itself (Imervue.image.avif_support)."""
from __future__ import annotations

import sys

import pytest
from PIL import Image, features

from Imervue.image import avif_support
from Imervue.image.avif_support import AVIF_EXTENSIONS, avif_available


def test_extensions():
    assert ".avif" in AVIF_EXTENSIONS
    assert all(e.startswith(".") and e == e.lower() for e in AVIF_EXTENSIONS)


def test_available_follows_pillows_own_plugin(monkeypatch):
    assert avif_available() is bool(features.check("avif"))
    monkeypatch.setattr(avif_support.features, "check", lambda name: None)
    assert avif_available() is False


def test_an_avif_opens_in_the_viewer_without_pillow_heif(tmp_path, monkeypatch):
    """The folder hint used to send AVIF users to pillow-heif, which has no AVIF opener."""
    if not avif_available():
        pytest.skip("this Pillow was built without libavif")
    path = tmp_path / "shot.avif"
    Image.new("RGB", (24, 12), (200, 30, 30)).save(path, quality=90)
    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    rgba = load_image_file(str(path))
    assert rgba.shape == (12, 24, 4)
    red, green, blue, alpha = (int(v) for v in rgba[6, 12])
    assert red > 150 > green and blue < 100
    assert alpha == 255
