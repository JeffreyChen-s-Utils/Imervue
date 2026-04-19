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
