"""Tests for SlideshowController start/stop mode handling.

A slideshow started from the thumbnail wall drops into deep zoom; stopping it
must hand the user back to the wall instead of stranding them in single-image
view. A fake viewer records the mode flips so no Qt OpenGL widget is needed
(only ``QTimer``, which the ``qapp`` fixture covers).
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.actions.slideshow import SlideshowController


class _FakeGui:
    def __init__(self, images, tile_grid_mode):
        self.model = SimpleNamespace(images=list(images))
        self.tile_grid_mode = tile_grid_mode
        self.current_index = 7
        self._slideshow_opacity = 1.0
        self.loaded: list[str] = []
        self.cleared = 0
        self.updates = 0

    def load_deep_zoom_image(self, path):
        self.loaded.append(path)

    def _clear_deep_zoom(self):
        self.cleared += 1

    def update(self):
        self.updates += 1


def _controller(qapp, images, tile_grid_mode):
    gui = _FakeGui(images, tile_grid_mode)
    return SlideshowController(gui, interval_ms=1000, fade=False), gui


def test_start_from_grid_enters_deep_zoom(qapp):
    ctrl, gui = _controller(qapp, ["a.png", "b.png"], tile_grid_mode=True)
    ctrl.start()
    assert ctrl.running is True
    assert gui.tile_grid_mode is False
    assert gui.current_index == 0
    assert gui.loaded == ["a.png"]
    ctrl.stop()  # don't leave a live QTimer running


def test_stop_returns_to_grid_when_started_from_grid(qapp):
    ctrl, gui = _controller(qapp, ["a.png", "b.png"], tile_grid_mode=True)
    ctrl.start()
    ctrl.stop()
    assert ctrl.running is False
    assert gui.tile_grid_mode is True       # back on the wall
    assert gui.cleared == 1                  # deep-zoom state released
    assert gui._slideshow_opacity == 1.0


def test_stop_stays_in_deep_zoom_when_started_from_deep_zoom(qapp):
    ctrl, gui = _controller(qapp, ["a.png"], tile_grid_mode=False)
    ctrl.start()
    assert gui.loaded == []                  # already in deep zoom; no re-enter
    ctrl.stop()
    assert gui.tile_grid_mode is False       # left where the user was
    assert gui.cleared == 0


def test_start_with_no_images_is_a_noop(qapp):
    ctrl, gui = _controller(qapp, [], tile_grid_mode=True)
    ctrl.start()
    assert ctrl.running is False
    assert gui.tile_grid_mode is True
    assert gui.loaded == []


def test_stop_after_images_cleared_does_not_force_grid(qapp):
    ctrl, gui = _controller(qapp, ["a.png"], tile_grid_mode=True)
    ctrl.start()
    gui.model.images = []                    # folder emptied mid-show
    ctrl.stop()
    assert gui.tile_grid_mode is False       # nothing to show -> no forced wall
    assert gui.cleared == 0


def test_resume_flag_is_reset_after_stop(qapp):
    ctrl, gui = _controller(qapp, ["a.png"], tile_grid_mode=True)
    ctrl.start()
    ctrl.stop()
    # A second start from deep zoom must not be flagged to resume to the grid.
    gui.tile_grid_mode = False
    ctrl.start()
    ctrl.stop()
    assert gui.tile_grid_mode is False
