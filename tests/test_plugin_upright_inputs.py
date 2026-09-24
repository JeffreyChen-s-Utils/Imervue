"""Plugins that decode a file themselves turn it upright by its EXIF orientation.

Their results are saved without EXIF, so a portrait phone photo (stored
sideways, with an orientation tag) came out sideways. They use Pillow's own
``ImageOps.exif_transpose`` so they keep working on older app releases.
"""
from __future__ import annotations

from PIL import Image


def _tagged_portrait(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6   # 40x20 stored, shown 20x40
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


def test_background_remover_loads_upright(qapp, tmp_path):
    from ai_background_remover.ai_background_remover import _RemoveBackgroundWorker
    assert _RemoveBackgroundWorker._load_image(_tagged_portrait(tmp_path)).size == (20, 40)


def test_smart_resize_peeks_the_upright_size(tmp_path):
    from ai_smart_resize.ai_smart_resize_plugin import _peek_image_size
    assert _peek_image_size(_tagged_portrait(tmp_path)) == (20, 40)
    plain = tmp_path / "plain.png"
    Image.new("RGB", (30, 10)).save(plain)
    assert _peek_image_size(str(plain)) == (30, 10)
    assert _peek_image_size(str(tmp_path / "missing.png")) == (1024, 1024)
