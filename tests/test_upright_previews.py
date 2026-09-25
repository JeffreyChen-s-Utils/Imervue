"""Every preview that decodes a file itself shows a tagged photo upright, as the viewer does.

Phones store a portrait shot as landscape pixels plus an EXIF orientation tag.
These loaders each opened the file with Pillow and ignored the tag, so the
compare view, inspector, reference panel, duplicate list, timeline and the
drag-out image showed such a photo on its side.
"""
from __future__ import annotations

import pytest
from PIL import Image


def _tagged_portrait(tmp_path):
    """40x20 stored pixels tagged 6: shown 20 wide, 40 tall."""
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


def _compare(path):
    from Imervue.gpu_image_view.actions.compare_dialog import _load_rgba_array
    arr = _load_rgba_array(path)
    return arr.shape[1], arr.shape[0]


def _inspector(path):
    from Imervue.gui.image_inspector_dialog import _load_preview_rgba
    arr = _load_preview_rgba(path)
    return arr.shape[1], arr.shape[0]


def _reference(path):
    from PySide6.QtCore import QSize

    from Imervue.gui.reference_panel_dialog import _load_preview_pixmap
    pix = _load_preview_pixmap(path, QSize(400, 400))
    return pix.width(), pix.height()


def _duplicates(path):
    from Imervue.gui.duplicate_detection_dialog import _make_thumbnail
    pix = _make_thumbnail(path, size=64)
    return pix.width(), pix.height()


def _drag_out(path):
    from Imervue.gpu_image_view.actions.drag_out import _build_preview_pixmap
    pix = _build_preview_pixmap(None, path)
    return pix.width(), pix.height()


def _smart_crop(path):
    from Imervue.gui.smart_crop_dialog import _load_rgba
    arr = _load_rgba(path)
    return arr.shape[1], arr.shape[0]


@pytest.mark.parametrize("load", [_compare, _inspector, _reference, _duplicates, _drag_out,
                                  _smart_crop])
def test_tagged_photo_preview_is_portrait(qapp, tmp_path, load):
    width, height = load(_tagged_portrait(tmp_path))
    assert height > width


def test_timeline_thumbnail_is_portrait(qapp, tmp_path):
    from Imervue.gui import timeline_view as tv
    worker = tv._TimelineThumbWorker(_tagged_portrait(tmp_path))
    seen = []
    worker.signals.done.connect(lambda _path, img, _ok: seen.append(img))
    worker.run()
    assert seen and seen[0].height() > seen[0].width()
