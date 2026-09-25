"""Paint drops, the GIF / video maker and the annotation editor decode like the viewer.

Each read the file with ``Image.open``: a portrait phone photo came in on its
side, its colour profile ignored, and (for the editors) a camera RAW as its
small embedded preview.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from _decode_samples import p3_green, tagged_portrait


def _fake_raw(monkeypatch, shape=(30, 50, 3)):
    from Imervue.gpu_image_view.images import image_loader
    monkeypatch.setattr(image_loader, "_load_raw",
                        lambda _p, thumbnail: np.full(shape, 90, dtype=np.uint8))


def test_load_shown_rgba_is_upright_and_srgb(tmp_path):
    from Imervue.image.shown import load_shown_rgba
    assert load_shown_rgba(tagged_portrait(tmp_path / "p.jpg")).shape == (40, 20, 4)
    red, green = load_shown_rgba(p3_green(tmp_path / "g.png"))[2, 2, :2]
    assert (int(red), int(green)) == (0, 255)


def test_pose_reference_is_upright(tmp_path):
    from Imervue.paint.pose_drop import load_pose_image
    assert load_pose_image(tagged_portrait(tmp_path / "p.jpg")).shape == (40, 20, 4)


def test_material_is_upright(tmp_path):
    from Imervue.paint.material_drop import load_material_image
    assert load_material_image(tagged_portrait(tmp_path / "p.jpg")).shape == (40, 20, 4)


def test_reference_thumbnail_is_upright(tmp_path):
    from Imervue.paint.reference_panel import load_thumbnail
    assert load_thumbnail(tagged_portrait(tmp_path / "p.jpg", size=(80, 40)), max_side=40).shape == (40, 20, 4)


def test_gif_maker_frames_are_upright_and_raw_is_developed(qapp, tmp_path, monkeypatch):
    from Imervue.gui.gif_video_dialog import _CreateWorker
    _fake_raw(monkeypatch)
    worker = _CreateWorker([], str(tmp_path / "out.gif"), "GIF", 10, 0, 0, True)
    assert worker._load_and_resize(str(tagged_portrait(tmp_path / "p.jpg"))).size == (20, 40)  # noqa: SLF001
    assert worker._load_and_resize(str(tmp_path / "shot.cr2")).size == (50, 30)  # noqa: SLF001
    worker.deleteLater()


def test_annotation_editor_opens_a_raw_at_full_size(qapp, tmp_path, monkeypatch):
    from Imervue.gui import annotation_dialog
    _fake_raw(monkeypatch)
    opened = []

    class _Dialog:
        def __init__(self, image, **_kwargs):
            opened.append(image.size)

        def exec(self):
            return 0

    monkeypatch.setattr(annotation_dialog, "AnnotationDialog", _Dialog)
    gui = SimpleNamespace(main_window=None)
    annotation_dialog.open_annotation_for_path(gui, str(tmp_path / "shot.cr2"))
    assert opened == [(50, 30)]
