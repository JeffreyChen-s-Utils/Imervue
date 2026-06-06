"""Tests for the multi-monitor mirror window.

``_PreviewPanel`` is a plain ``QLabel`` and the controller logic is exercised
with light fakes, so no ``QOpenGLWidget`` is constructed and the headless-CI
skip marker is not required.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QImage

from Imervue.gui.multi_monitor_window import (
    MultiMonitorController,
    _PreviewPanel,
    array_to_qimage,
    choose_mirror_screen_index,
)


class TestChooseMirrorScreenIndex:
    def test_prefers_remembered_non_primary_screen(self):
        names = ["DELL", "HP", "LG"]
        # Primary is index 0; remembered "LG" should win over first-other "HP".
        assert choose_mirror_screen_index(names, 0, "LG") == 2

    def test_falls_back_to_first_non_primary(self):
        names = ["A", "B", "C"]
        assert choose_mirror_screen_index(names, 1, None) == 0

    def test_ignores_preferred_when_it_is_the_primary(self):
        names = ["A", "B"]
        # Preferred names the primary screen → skip it, use the other one.
        assert choose_mirror_screen_index(names, 0, "A") == 1

    def test_ignores_preferred_when_absent(self):
        names = ["A", "B"]
        assert choose_mirror_screen_index(names, 0, "GONE") == 1

    def test_single_screen_returns_primary(self):
        assert choose_mirror_screen_index(["only"], 0, None) == 0
        assert choose_mirror_screen_index(["only"], 0, "only") == 0


class TestArrayToQImage:
    def test_rgba_array(self, qapp):
        img = array_to_qimage(np.zeros((4, 5, 4), dtype=np.uint8))
        assert (img.width(), img.height()) == (5, 4)
        assert img.format() == QImage.Format.Format_RGBA8888

    def test_rgb_array(self, qapp):
        img = array_to_qimage(np.zeros((3, 6, 3), dtype=np.uint8))
        assert (img.width(), img.height()) == (6, 3)
        assert img.format() == QImage.Format.Format_RGB888

    def test_detaches_from_source_buffer(self, qapp):
        arr = np.zeros((2, 2, 4), dtype=np.uint8)
        img = array_to_qimage(arr)
        arr[:] = 255  # mutate source after conversion
        # ``.copy()`` means the QImage owns its pixels — unaffected.
        assert img.pixelColor(0, 0).red() == 0

    @pytest.mark.parametrize(
        "shape",
        [(2, 2), (2, 2, 1), (2, 2, 2)],
    )
    def test_invalid_channel_count_raises(self, qapp, shape):
        with pytest.raises(ValueError):
            array_to_qimage(np.zeros(shape, dtype=np.uint8))


class TestPreviewPanel:
    def test_set_array_produces_pixmap(self, qapp):
        panel = _PreviewPanel()
        panel.resize(100, 100)
        panel.set_array(np.zeros((10, 10, 3), dtype=np.uint8))
        assert not panel.pixmap().isNull()

    def test_set_array_none_shows_placeholder_text(self, qapp):
        panel = _PreviewPanel()
        panel.set_array(None)
        assert panel.text()  # localised "No image"


class _FakeViewer:
    def __init__(self):
        self.on_deep_zoom_displayed = None
        self.deep_zoom = None


class _FakeMainWindow:
    def __init__(self):
        self.viewer = _FakeViewer()


class _FakeWindow:
    def __init__(self):
        self.arrays: list = []
        self.images: list = []

    def set_array(self, arr):
        self.arrays.append(arr)

    def set_image(self, path):
        self.images.append(path)


class _FakeDeepZoom:
    def __init__(self, base):
        self.levels = [base]


class TestController:
    def test_deep_zoom_array_is_mirrored_and_forwarded(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        forwarded: list = []
        ctrl._prev_on_displayed = forwarded.append
        ctrl._window = _FakeWindow()

        arr = np.zeros((2, 2, 3), dtype=np.uint8)
        ctrl._on_deep_zoom_array(arr)

        assert forwarded == [arr]              # chained to prior hook
        assert ctrl._window.arrays == [arr]    # and shown on the mirror

    def test_deep_zoom_array_tolerates_no_prior_hook(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        ctrl._prev_on_displayed = None
        ctrl._window = _FakeWindow()
        ctrl._on_deep_zoom_array(np.zeros((2, 2, 4), dtype=np.uint8))
        assert len(ctrl._window.arrays) == 1

    def test_mirror_current_pushes_edited_base_level(self):
        mw = _FakeMainWindow()
        base = np.zeros((2, 2, 3), dtype=np.uint8)
        mw.viewer.deep_zoom = _FakeDeepZoom(base)
        ctrl = MultiMonitorController(mw)
        ctrl._window = _FakeWindow()

        ctrl._mirror_current()
        assert ctrl._window.arrays == [base]

    def test_mirror_current_without_image_shows_placeholder(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        ctrl._window = _FakeWindow()
        ctrl._mirror_current()
        assert ctrl._window.images == [None]
