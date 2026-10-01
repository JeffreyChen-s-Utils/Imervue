"""Tests for hover preview loader and controller state machine."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

_rng = np.random.default_rng(seed=0xC0FFEE)


@pytest.fixture
def hover_mod(qapp):
    from Imervue.gui import hover_preview as m
    return m


@pytest.fixture
def sample_png(tmp_path):
    p = tmp_path / "sample.png"
    Image.fromarray(_rng.integers(0, 256, (200, 300, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class TestLoadPreview:
    def test_returns_none_for_missing_file(self, hover_mod, tmp_path):
        assert hover_mod._load_preview(str(tmp_path / "ghost.png")) is None

    def test_returns_none_for_non_image(self, hover_mod, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not a png")
        assert hover_mod._load_preview(str(bad)) is None

    def test_unexpected_error_propagates(self, hover_mod, sample_png, monkeypatch):
        def boom(_path):
            raise RuntimeError("bug")

        monkeypatch.setattr(hover_mod.Image, "open", boom)
        with pytest.raises(RuntimeError):
            hover_mod._load_preview(sample_png)

    def test_loads_pixmap_for_valid_image(self, hover_mod, sample_png):
        pm = hover_mod._load_preview(sample_png, max_edge=256)
        assert pm is not None
        assert not pm.isNull()
        # 300 long edge → 256
        assert max(pm.width(), pm.height()) == 256

    def test_does_not_upscale_small_images(self, hover_mod, tmp_path):
        p = tmp_path / "tiny.png"
        Image.fromarray(np.zeros((30, 40, 3), dtype=np.uint8)).save(str(p))
        pm = hover_mod._load_preview(str(p), max_edge=512)
        # Original dimensions preserved
        assert pm.width() == 40
        assert pm.height() == 30

    def test_a_sixteen_bit_grey_picture_previews_as_a_gradient(self, hover_mod, tmp_path):
        p = tmp_path / "grey16.png"
        Image.fromarray(np.array([[0, 32768, 65535]], dtype=np.uint16)).save(str(p))
        image = hover_mod._load_preview(str(p)).toImage()
        assert [image.pixelColor(x, 0).red() for x in range(3)] == [0, 128, 255]


class TestUprightAndCaption:
    def test_tagged_photo_previews_upright(self, hover_mod, tmp_path):
        exif = Image.Exif()
        exif[0x0112] = 6
        p = tmp_path / "portrait.jpg"
        Image.new("RGB", (40, 20)).save(p, exif=exif)
        pm = hover_mod._load_preview(str(p), max_edge=512)
        assert (pm.width(), pm.height()) == (20, 40)

    def test_caption_shows_the_image_size_not_the_scaled_preview(self, hover_mod, tmp_path):
        """It printed the pixmap's size: a 900x600 image showed as its 512x341 preview."""
        big = tmp_path / "big.png"
        Image.new("RGB", (900, 600)).save(big)
        popup = hover_mod.HoverPreviewPopup()
        try:
            from PySide6.QtCore import QPoint
            popup.show_for(str(big), QPoint(0, 0))
            assert popup._image_label.pixmap().width() == 512
            assert "900×600" in popup._caption.text()
        finally:
            popup.hide()
            popup.deleteLater()


class TestController:
    def test_arm_starts_timer(self, hover_mod, qapp):
        from PySide6.QtCore import QPoint
        ctrl = hover_mod.HoverPreviewController()
        ctrl.arm("some_path.png", QPoint(100, 100))
        assert ctrl._timer.isActive()

    def test_disarm_stops_timer(self, hover_mod, qapp):
        from PySide6.QtCore import QPoint
        ctrl = hover_mod.HoverPreviewController()
        ctrl.arm("some_path.png", QPoint(0, 0))
        ctrl.disarm()
        assert not ctrl._timer.isActive()
        assert ctrl._pending_path is None

    def test_rearm_same_path_does_not_restart(self, hover_mod, qapp):
        from PySide6.QtCore import QPoint
        ctrl = hover_mod.HoverPreviewController()
        ctrl.arm("same.png", QPoint(0, 0))
        # Second arm on same path while timer pending — should keep current timer
        ctrl.arm("same.png", QPoint(10, 10))
        assert ctrl._pending_path == "same.png"
        assert ctrl._pending_pos == QPoint(10, 10)

    def test_rearm_different_path_switches_target(self, hover_mod, qapp):
        from PySide6.QtCore import QPoint
        ctrl = hover_mod.HoverPreviewController()
        ctrl.arm("a.png", QPoint(0, 0))
        ctrl.arm("b.png", QPoint(5, 5))
        assert ctrl._pending_path == "b.png"
