"""Qt smoke test for the crop/straighten aspect-ratio preset wiring.

Plain QDialog (no QOpenGLWidget) so no headless-CI skip. A bare QWidget stands
in for the viewer — the aspect wiring touched here never calls viewer methods.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from Imervue.gui.crop_straighten_dialog import CropStraightenDialog


def test_aspect_preset_fills_crop_fields(qapp, sample_png):
    dlg = CropStraightenDialog(QWidget(), str(sample_png))
    # sample_png is 64x64 (aspect 1.0); a 16:9 crop is width-limited → full
    # width, 9/16 height, centred vertically.
    dlg._aspect.setCurrentText("16:9")
    assert dlg._crop_w.value() == pytest.approx(1.0, abs=1e-3)
    assert dlg._crop_h.value() == pytest.approx(9 / 16, abs=1e-3)
    assert dlg._crop_x.value() == pytest.approx(0.0, abs=1e-3)
    assert dlg._crop_y.value() == pytest.approx((1 - 9 / 16) / 2, abs=1e-3)


def test_free_preset_does_not_reset_crop(qapp, sample_png):
    dlg = CropStraightenDialog(QWidget(), str(sample_png))
    dlg._aspect.setCurrentText("16:9")
    h_after_ratio = dlg._crop_h.value()
    dlg._aspect.setCurrentText("free")  # must not clobber the existing crop
    assert dlg._crop_h.value() == pytest.approx(h_after_ratio)


def _tagged_portrait(tmp_path):
    from PIL import Image
    exif = Image.Exif()
    exif[0x0112] = 6   # 40x20 stored, shown 20x40
    path = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    return str(path)


def test_aspect_uses_the_upright_size(qapp, tmp_path):
    dlg = CropStraightenDialog(QWidget(), _tagged_portrait(tmp_path))
    assert dlg._probe_image_aspect() == pytest.approx(0.5)


def test_worker_saves_the_upright_image(qapp, tmp_path):
    """Its output has no EXIF, so the stored sideways pixels would stay sideways."""
    from PIL import Image

    from Imervue.gui.crop_straighten_dialog import _Worker
    out = tmp_path / "out.png"
    worker = _Worker(_tagged_portrait(tmp_path), str(out), 0.0, None)
    worker.run()
    with Image.open(out) as saved:
        assert saved.size == (20, 40)
