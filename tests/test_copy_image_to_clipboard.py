"""Tests for Ctrl+C: the clipboard gets the image as the viewer shows it."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from _decode_samples import tagged_portrait
from Imervue.gpu_image_view.actions.keyboard_actions import copy_image_to_clipboard


def _gui(path, deep_zoom=None):
    return SimpleNamespace(model=SimpleNamespace(images=[str(path)]), current_index=0,
                           deep_zoom=deep_zoom)


def test_copies_the_displayed_pyramid_base(qapp, fake_clipboard, tmp_path):
    """The shown pixels carry the develop recipe; the file on disk does not."""
    base = np.zeros((6, 10, 4), dtype=np.uint8)
    base[..., 0] = 200
    base[..., 3] = 255
    copy_image_to_clipboard(_gui(tmp_path / "x.png", SimpleNamespace(levels=[base])))
    image = fake_clipboard.image()
    assert (image.width(), image.height()) == (10, 6)
    assert image.pixelColor(0, 0).red() == 200


def test_without_a_pyramid_the_file_is_decoded_upright(qapp, fake_clipboard, tmp_path):
    """QImage(path) pasted a portrait phone photo on its side."""
    copy_image_to_clipboard(_gui(tagged_portrait(tmp_path / "p.jpg")))
    image = fake_clipboard.image()
    assert (image.width(), image.height()) == (20, 40)


def test_unreadable_file_leaves_the_clipboard_alone(qapp, fake_clipboard, tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"nope")
    copy_image_to_clipboard(_gui(bad))
    assert fake_clipboard.image().isNull()
