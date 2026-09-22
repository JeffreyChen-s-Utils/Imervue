"""Tests for the pure helpers extracted into ``overlay_painter``.

These cover the text/geometry logic that used to live inline in
``GPUImageView``'s OSD / Debug-HUD / pixel-view methods. They are pure
Python (no Qt, no GL) so they run on headless CI without a context.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.gpu_image_view.overlay_painter import (
    OverlayPainter,
    _rgba_to_pixmap,
    _run_overlay_layers,
)


"""Tests for the pure helpers extracted into ``overlay_painter``.

These cover the text/geometry logic that used to live inline in
``GPUImageView``'s OSD / Debug-HUD / pixel-view methods. They are pure
Python (no Qt, no GL) so they run on headless CI without a context.
"""


def _video_view(images, current_index):
    return SimpleNamespace(
        model=SimpleNamespace(images=images), current_index=current_index,
    )


def test_current_is_video_true():
    op = OverlayPainter(_video_view(["a.png", "clip.mp4"], 1))
    assert op._current_is_video() is True


def test_current_is_video_false_for_image():
    op = OverlayPainter(_video_view(["a.png"], 0))
    assert op._current_is_video() is False


def test_current_is_video_empty():
    op = OverlayPainter(_video_view([], 0))
    assert op._current_is_video() is False


def test_current_is_video_out_of_range():
    op = OverlayPainter(_video_view(["clip.mp4"], 9))
    assert op._current_is_video() is False


def test_rgba_to_pixmap_preserves_dimensions(qapp):
    arr = np.zeros((12, 20, 4), dtype=np.uint8)
    arr[..., 0] = 255  # opaque red
    arr[..., 3] = 255
    pixmap = _rgba_to_pixmap(arr)
    assert not pixmap.isNull()
    assert pixmap.width() == 20
    assert pixmap.height() == 12


def test_rgba_to_pixmap_accepts_non_contiguous(qapp):
    # A sliced (non-contiguous) view must still convert without raising.
    base = np.zeros((10, 10, 4), dtype=np.uint8)
    base[..., 3] = 255
    view = base[::2, ::2]
    pixmap = _rgba_to_pixmap(view)
    assert pixmap.width() == 5
    assert pixmap.height() == 5


# ``collect_layers`` is pure logic (no GL, no Qt construction): it inspects the
# view's browse-state flags and returns the active overlay draw methods. Testing
# it with a fake view guards every ``view._*`` access it makes, so a renamed or
# typo'd flag is caught here rather than only at paint time on a real widget.
def _overlay_view(**kw):
    images = kw.pop("images", [])
    base = {
        "tile_grid_mode": False,
        "deep_zoom": None,
        "_animation": None,
        "_pixel_view": False,
        "zoom": 1.0,
        "_filmstrip_enabled": True,
        "_deep_zoom_loading": None,
        "tile_rects": [],
        "_show_histogram": False,
        "_show_osd": False,
        "_show_debug_hud": False,
        "_loupe_enabled": False,
        "_hover_image_xy": None,
        "_zoom_band_active": False,
        "_zoom_band_start": None,
        "_zoom_band_end": None,
    }
    base.update(kw)
    view = SimpleNamespace(**base)
    view.model = SimpleNamespace(images=images)
    return view


def test_collect_layers_empty_when_idle():
    assert OverlayPainter(_overlay_view()).collect_layers() == []


def test_collect_layers_filmstrip_active_in_deep_zoom_multi_image():
    overlay = OverlayPainter(_overlay_view(deep_zoom=object(),
                                           images=["a.png", "b.png"]))
    assert overlay.draw_filmstrip in overlay.collect_layers()


def test_collect_layers_filmstrip_inactive_single_image():
    overlay = OverlayPainter(_overlay_view(deep_zoom=object(), images=["a.png"]))
    assert overlay.draw_filmstrip not in overlay.collect_layers()


def test_collect_layers_loupe_active_when_hovering():
    overlay = OverlayPainter(_overlay_view(
        deep_zoom=object(), _loupe_enabled=True, _hover_image_xy=(5, 5)))
    assert overlay.draw_loupe in overlay.collect_layers()


def test_collect_layers_loading_preview_and_pill_during_gap():
    overlay = OverlayPainter(_overlay_view(_deep_zoom_loading="x.png",
                                           deep_zoom=None))
    layers = overlay.collect_layers()
    assert overlay.draw_loading_preview in layers
    assert overlay.draw_loading_pill in layers


def test_collect_layers_zoom_band_active_while_framing():
    overlay = OverlayPainter(_overlay_view(
        deep_zoom=object(), _zoom_band_active=True,
        _zoom_band_start=object(), _zoom_band_end=object()))
    assert overlay.draw_zoom_band in overlay.collect_layers()


def test_collect_layers_tile_grid_layers_active():
    overlay = OverlayPainter(_overlay_view(
        tile_grid_mode=True, tile_rects=[(0, 0, 1, 1, "a.png")]))
    assert overlay.draw_tile_overlays in overlay.collect_layers()


class TestRunOverlayLayers:
    def test_one_failing_layer_does_not_skip_the_others(self):
        calls = []

        def good_a(_p):
            calls.append("a")

        def boom(_p):
            raise ValueError("layer blew up")

        def good_b(_p):
            calls.append("b")

        failed = _run_overlay_layers(object(), [good_a, boom, good_b])
        # The filmstrip / minimap chrome (good layers) still draw despite the
        # bad one — the whole overlay no longer vanishes for the frame.
        assert calls == ["a", "b"]
        assert failed == ["boom"]

    def test_all_layers_run_when_none_fail(self):
        calls = []
        layers = [lambda _p, i=i: calls.append(i) for i in range(3)]
        assert _run_overlay_layers(object(), layers) == []
        assert calls == [0, 1, 2]

    def test_empty_layer_list_is_a_no_op(self):
        assert _run_overlay_layers(object(), []) == []

    def test_failure_uses_layer_name(self):
        def draw_video_badge(_p):
            raise RuntimeError("no poster")

        assert _run_overlay_layers(object(), [draw_video_badge]) == [
            "draw_video_badge"]
