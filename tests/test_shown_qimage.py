"""Tests for decoding a file into a QImage the way the viewer shows it."""
from __future__ import annotations

import numpy as np

from _decode_samples import p3_green, tagged_portrait
from Imervue.gui.shown_qimage import shown_qimage


def test_tagged_photo_is_upright(qapp, tmp_path):
    """QImage(path) left a portrait phone photo on its side."""
    img = shown_qimage(str(tagged_portrait(tmp_path / "p.jpg")))
    assert (img.width(), img.height()) == (20, 40)


def test_colour_profile_is_converted(qapp, tmp_path):
    colour = shown_qimage(str(p3_green(tmp_path / "g.png"))).pixelColor(2, 2)
    assert (colour.red(), colour.green()) == (0, 255)


def test_max_edge_scales_the_long_side(qapp, tmp_path):
    img = shown_qimage(str(tagged_portrait(tmp_path / "p.jpg", size=(800, 400))), max_edge=100)
    assert (img.width(), img.height()) == (50, 100)


def test_raw_is_developed(qapp, tmp_path, monkeypatch):
    from Imervue.gpu_image_view.images import image_loader
    monkeypatch.setattr(image_loader, "_load_raw",
                        lambda _p, thumbnail: np.full((30, 50, 3), 90, dtype=np.uint8))
    img = shown_qimage(str(tmp_path / "shot.cr2"))
    assert (img.width(), img.height()) == (50, 30)


def test_unreadable_file_is_a_null_image(qapp, tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"nope")
    assert shown_qimage(str(bad)).isNull()
    assert shown_qimage(str(tmp_path / "gone.png")).isNull()
