"""Contract tests for :class:`OverlayPainter` and its layer mixins.

They pin what the overlay must keep doing however its methods are spread over
modules: the exact draw order of every layer in each viewer state, the
placeholder / fade-in repaint pump, the per-image caches, and that every layer
paints onto a real ``QImage`` without raising (a layer that lost an import or
a helper would otherwise only be logged and skipped at paint time).
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap

from Imervue.gpu_image_view import overlay_painter as op_mod
from Imervue.gpu_image_view import overlay_tiles
from Imervue.gpu_image_view.overlay_painter import OverlayPainter

_VIEW_W, _VIEW_H = 320, 240
_FAR_FUTURE = 10 ** 9


def _layer_names(view) -> list[str]:
    return [layer.__name__ for layer in OverlayPainter(view).collect_layers()]


def _state_view(**kw):
    images = kw.pop("images", [])
    base = {
        "tile_grid_mode": False,
        "deep_zoom": None,
        "_animation": None,
        "_pixel_view": False,
        "zoom": 1.0,
        "_filmstrip_enabled": False,
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
        "current_index": 0,
    }
    base.update(kw)
    view = SimpleNamespace(**base)
    view.model = SimpleNamespace(images=images)
    return view


# ---------------------------------------------------------------------------
# Draw order
# ---------------------------------------------------------------------------
class TestDrawOrder:
    def test_deep_zoom_layers_in_order(self):
        view = _state_view(
            deep_zoom=object(), images=["clip.mp4", "b.png"],
            _filmstrip_enabled=True, _show_histogram=True, _show_osd=True,
            _show_debug_hud=True, _pixel_view=True, zoom=4.0,
            _animation=SimpleNamespace(is_animated=True),
            _quick_meta_hud=("5 stars", time.monotonic() + _FAR_FUTURE),
            _loupe_enabled=True, _hover_image_xy=(1, 1),
            _zoom_band_active=True, _zoom_band_start=object(),
            _zoom_band_end=object(),
        )
        assert _layer_names(view) == [
            "draw_filmstrip", "draw_zoom_indicator", "draw_histogram",
            "draw_anim_indicator", "draw_osd", "draw_debug_hud",
            "draw_quick_meta_hud", "draw_pixel_view", "draw_loupe",
            "draw_zoom_band", "draw_video_badge",
        ]

    def test_loading_gap_layers_in_order(self):
        view = _state_view(
            images=["a.png", "b.png"], _filmstrip_enabled=True,
            _deep_zoom_loading="a.png", _deep_zoom_error=("a.png", "boom"),
            _show_debug_hud=True,
        )
        assert _layer_names(view) == [
            "draw_loading_preview", "draw_filmstrip", "draw_debug_hud",
            "draw_loading_pill", "draw_deep_zoom_error",
        ]

    def test_tile_wall_layers_in_order(self):
        view = _state_view(
            tile_grid_mode=True, tile_rects=[(0, 0, 1, 1, "a.png")],
            _folder_scan_active=True, _loupe_enabled=True,
            _hover_tile_path="a.png", tile_cache={"a.png": object()},
            _filmstrip_enabled=True, deep_zoom=object(),
            _deep_zoom_loading="a.png", _deep_zoom_error=("a.png", "x"),
        )
        assert _layer_names(view) == [
            "draw_tile_overlays", "draw_tile_state_overlays",
            "draw_wall_loading", "draw_tile_loupe",
        ]

    def test_tile_wall_without_rects_keeps_only_state_layer(self):
        view = _state_view(tile_grid_mode=True, images=["a.png"])
        assert _layer_names(view) == ["draw_tile_state_overlays"]

    def test_tile_loupe_needs_cached_hover_tile(self):
        view = _state_view(tile_grid_mode=True, images=["a.png"],
                           _loupe_enabled=True, _hover_tile_path="a.png",
                           tile_cache={})
        assert "draw_tile_loupe" not in _layer_names(view)

    @pytest.mark.parametrize(("zoom", "pixel_view", "expected"), [
        (3.99, True, False),
        (4.0, True, True),
        (8.0, False, False),
    ])
    def test_pixel_view_zoom_threshold(self, zoom, pixel_view, expected):
        view = _state_view(deep_zoom=object(), zoom=zoom, _pixel_view=pixel_view)
        assert ("draw_pixel_view" in _layer_names(view)) is expected

    def test_static_animation_has_no_indicator(self):
        view = _state_view(deep_zoom=object(),
                           _animation=SimpleNamespace(is_animated=False))
        assert "draw_anim_indicator" not in _layer_names(view)

    def test_zoom_band_needs_both_corners(self):
        view = _state_view(deep_zoom=object(), _zoom_band_active=True,
                           _zoom_band_start=object(), _zoom_band_end=None)
        assert "draw_zoom_band" not in _layer_names(view)

    def test_error_layer_hidden_once_image_loaded(self):
        view = _state_view(deep_zoom=object(), _deep_zoom_error=("a.png", "x"))
        assert "draw_deep_zoom_error" not in _layer_names(view)


# ---------------------------------------------------------------------------
# HUD timing + fade pump
# ---------------------------------------------------------------------------
class TestQuickHud:
    def test_inactive_without_hud(self):
        assert OverlayPainter(SimpleNamespace())._quick_hud_active() is False

    def test_inactive_once_expired(self):
        view = SimpleNamespace(_quick_meta_hud=("x", time.monotonic() - 1))
        assert OverlayPainter(view)._quick_hud_active() is False

    def test_active_before_expiry(self):
        view = SimpleNamespace(_quick_meta_hud=("x", time.monotonic() + 60))
        assert OverlayPainter(view)._quick_hud_active() is True

    def test_expired_hud_is_cleared_without_painting(self):
        view = SimpleNamespace(_quick_meta_hud=("x", time.monotonic() - 1))
        OverlayPainter(view).draw_quick_meta_hud(None)
        assert view._quick_meta_hud is None


class TestTilesFading:
    def test_no_load_times(self):
        assert OverlayPainter(SimpleNamespace())._tiles_fading() is False

    def test_recent_tile_is_fading(self):
        view = SimpleNamespace(_tile_load_times={"a": time.monotonic()})
        assert OverlayPainter(view)._tiles_fading() is True

    def test_old_tile_is_settled(self):
        view = SimpleNamespace(_tile_load_times={"a": time.monotonic() - 3600})
        assert OverlayPainter(view)._tiles_fading() is False


class _FakeTimer:
    def __init__(self, active: bool) -> None:
        self.active = active
        self.stopped = False

    def isActive(self) -> bool:  # noqa: N802 - mirrors QTimer
        return self.active

    def stop(self) -> None:
        self.stopped = True
        self.active = False


class TestPlaceholderPump:
    def _view(self, **kw):
        view = SimpleNamespace(
            tile_grid_mode=True, placeholder_rects=[], _tile_load_times={},
            _folder_scan_active=False, model=SimpleNamespace(images=["a"]),
            updated=[],
        )
        view.__dict__.update(kw)
        view.update = lambda: view.updated.append(True)
        return view

    def test_placeholders_keep_repainting(self):
        view = self._view(placeholder_rects=[(0, 0, 1, 1)])
        OverlayPainter(view).tick_placeholder()
        assert view.updated == [True]

    def test_fading_tiles_keep_repainting(self):
        view = self._view(_tile_load_times={"a": time.monotonic()})
        OverlayPainter(view).tick_placeholder()
        assert view.updated == [True]

    def test_idle_wall_stops_the_timer(self):
        view = self._view()
        overlay = OverlayPainter(view)
        timer = _FakeTimer(active=True)
        overlay._placeholder_timer = timer
        overlay.tick_placeholder()
        assert timer.stopped is True
        assert view.updated == []

    def test_leaving_the_wall_stops_the_timer(self):
        view = self._view(tile_grid_mode=False, placeholder_rects=[(0, 0, 1, 1)])
        overlay = OverlayPainter(view)
        timer = _FakeTimer(active=True)
        overlay._placeholder_timer = timer
        overlay.tick_placeholder()
        assert timer.stopped is True
        assert view.updated == []

    def test_inactive_timer_is_left_alone(self):
        overlay = OverlayPainter(self._view())
        timer = _FakeTimer(active=False)
        overlay._placeholder_timer = timer
        overlay.tick_placeholder()
        assert timer.stopped is False

    def test_ensure_fade_pump_creates_one_running_timer(self, qapp):
        owner = QObject()
        overlay = OverlayPainter(owner)
        try:
            overlay.ensure_fade_pump()
            timer = overlay._placeholder_timer
            assert timer is not None
            assert timer.isActive()
            assert timer.interval() == overlay_tiles._PLACEHOLDER_TICK_MS
            assert timer.parent() is owner
            timer.stop()
            overlay.ensure_fade_pump()
            assert overlay._placeholder_timer is timer
            assert timer.isActive()
        finally:
            overlay._placeholder_timer.stop()
            owner.deleteLater()


# ---------------------------------------------------------------------------
# Per-image caches
# ---------------------------------------------------------------------------
class TestCaches:
    def test_exif_lines_served_from_cache(self):
        view = SimpleNamespace(_exif_osd_cache=("a.jpg", ["ISO 100"]))
        assert OverlayPainter(view)._exif_osd_lines("a.jpg") == ["ISO 100"]

    def test_filmstrip_pixmap_cache_hit(self):
        sentinel = object()
        view = SimpleNamespace(_filmstrip_thumb_cache={"a.png": sentinel})
        assert OverlayPainter(view)._filmstrip_pixmap("a.png") is sentinel

    def test_filmstrip_pixmap_miss_requests_thumbnail(self):
        requested = []
        view = SimpleNamespace(_filmstrip_thumb_cache={}, tile_cache={},
                               _ensure_filmstrip_thumbnail=requested.append)
        assert OverlayPainter(view)._filmstrip_pixmap("a.png") is None
        assert requested == ["a.png"]
        assert view._filmstrip_thumb_cache == {}

    def test_filmstrip_pixmap_built_from_tile_cache(self, qapp):
        arr = np.zeros((6, 8, 4), dtype=np.uint8)
        view = SimpleNamespace(_filmstrip_thumb_cache={},
                               tile_cache={"a.png": arr})
        pixmap = OverlayPainter(view)._filmstrip_pixmap("a.png")
        assert isinstance(pixmap, QPixmap)
        assert (pixmap.width(), pixmap.height()) == (8, 6)
        assert view._filmstrip_thumb_cache["a.png"] is pixmap

    def test_histogram_skips_without_deep_zoom(self):
        view = SimpleNamespace(deep_zoom=None)
        OverlayPainter(view).draw_histogram(None)

    def test_histogram_skips_out_of_range_index(self):
        view = SimpleNamespace(deep_zoom=object(), current_index=3,
                               model=SimpleNamespace(images=["a.png"]))
        OverlayPainter(view).draw_histogram(None)


# ---------------------------------------------------------------------------
# Every layer paints onto a real QImage
# ---------------------------------------------------------------------------
class _PaintView(QObject):
    """Minimal ``GPUImageView`` stand-in that every overlay layer can read."""

    def __init__(self, **state) -> None:
        super().__init__()
        self.__dict__.update(state)
        self.repaints = 0

    def width(self) -> int:
        return _VIEW_W

    def height(self) -> int:
        return _VIEW_H

    def devicePixelRatio(self) -> float:  # noqa: N802 - mirrors QWidget
        return 1.0

    def update(self) -> None:
        self.repaints += 1

    def _current_minimap_rect(self):
        return (200, 150, 100, 60)

    def _current_path(self):
        return self.model.images[self.current_index]

    def _ensure_filmstrip_thumbnail(self, path) -> None:
        self.requested.append(path)


def _rgba(height: int, width: int) -> np.ndarray:
    arr = np.full((height, width, 4), 200, dtype=np.uint8)
    arr[..., 3] = 255
    return arr


def _common_state(images) -> dict:
    lang = {}
    return {
        "model": SimpleNamespace(images=images),
        "current_index": 0,
        "main_window": SimpleNamespace(
            language_wrapper=SimpleNamespace(language_word_dict=lang)),
        "tile_cache": {}, "tile_textures": {}, "tile_rects": [],
        "_filmstrip_thumb_cache": {}, "requested": [],
        "_vram_usage": 10 * 1024 * 1024, "_vram_limit": 100 * 1024 * 1024,
        "_prefetch_cache": {}, "_prefetch_workers": [],
        "thread_pool": SimpleNamespace(activeThreadCount=lambda: 1,
                                       maxThreadCount=lambda: 4),
        "_load_generation": 3, "_show_debug_hud": True,
        "_quick_meta_hud": ("Rated 5", time.monotonic() + _FAR_FUTURE),
        "_animation": None, "_deep_zoom_loading": None,
        "_zoom_band_active": False, "_zoom_band_start": None,
        "_zoom_band_end": None, "_loupe_enabled": True,
        "_hover_image_xy": None, "_pixel_view": True,
    }


def _deep_zoom_view(tmp_path):
    path = str(tmp_path / "clip.mp4")
    state = _common_state([path, str(tmp_path / "b.png")])
    state.update({
        "tile_grid_mode": False,
        "deep_zoom": SimpleNamespace(levels=[_rgba(64, 64), _rgba(16, 16)]),
        "zoom": 8.0, "dz_offset_x": 0.0, "dz_offset_y": 0.0,
        "_filmstrip_enabled": True,
        "_browse": SimpleNamespace(filmstrip_strip_width=lambda: _VIEW_W),
        "_show_histogram": True, "_histogram_cache": None,
        "_show_osd": True, "_exif_osd_cache": (path, ["ISO 100"]),
        "_animation": SimpleNamespace(
            is_animated=True, current_frame=0, total_frames=3, paged=False,
            playing=True, speed=1.0),
        "_hover_image_xy": (5, 5), "_loupe_magnification": 4.0,
        "_zoom_band_active": True, "_zoom_band_start": QPoint(10, 10),
        "_zoom_band_end": QPoint(60, 50),
    })
    state["tile_cache"] = {path: _rgba(12, 16)}
    return _PaintView(**state)


def _tile_wall_view(tmp_path):
    tile = tmp_path / "a.mp4"
    tile.write_bytes(b"")
    state = _common_state([])
    state.update({
        "tile_grid_mode": True, "deep_zoom": None, "zoom": 1.0,
        "_filmstrip_enabled": False, "_folder_scan_active": True,
        "tile_rects": [(10, 10, 74, 74, str(tile))],
        "placeholder_rects": [(80, 10, 144, 74)],
        "error_tile_rects": [(150, 10, 214, 74, "e.png")],
        "missing_tile_rects": [(220, 10, 284, 74, "m.png")],
        "_stack_members": {str(tile): ["x", "y"]},
        "_timeline_grouping_enabled": True,
        "_tile_load_times": {}, "_hover_tile_path": str(tile),
    })
    state["tile_cache"] = {str(tile): _rgba(32, 32)}
    return _PaintView(**state)


def _loading_view(tmp_path):
    first = str(tmp_path / "a.png")
    state = _common_state([first, str(tmp_path / "b.png")])
    state.update({
        "tile_grid_mode": False, "deep_zoom": None, "zoom": 1.0,
        "_filmstrip_enabled": True,
        "_browse": SimpleNamespace(filmstrip_strip_width=lambda: _VIEW_W),
        "_deep_zoom_loading": first,
        "_deep_zoom_error": (first, "decode failed"),
    })
    state["tile_cache"] = {first: _rgba(12, 16)}
    return _PaintView(**state)


def _paint_each_layer(view) -> list[str]:
    overlay = OverlayPainter(view)
    target = QImage(_VIEW_W, _VIEW_H, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    names = []
    try:
        for layer in overlay.collect_layers():
            layer(painter)
            names.append(layer.__name__)
    finally:
        painter.end()
        if overlay._placeholder_timer is not None:
            overlay._placeholder_timer.stop()
    return names


def _paint_whole_overlay(view) -> QImage:
    overlay = OverlayPainter(view)
    target = QImage(_VIEW_W, _VIEW_H, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    try:
        overlay.paint(painter)
    finally:
        painter.end()
        if overlay._placeholder_timer is not None:
            overlay._placeholder_timer.stop()
    return target


def _opaque_pixel_count(image: QImage) -> int:
    count = 0
    for y in range(0, image.height(), 4):
        for x in range(0, image.width(), 4):
            if image.pixelColor(x, y).alpha() > 0:
                count += 1
    return count


class TestLayersPaint:
    def test_deep_zoom_layers_paint(self, qapp, tmp_path):
        view = _deep_zoom_view(tmp_path)
        names = _paint_each_layer(view)
        assert names[0] == "draw_filmstrip"
        assert names[-1] == "draw_video_badge"
        cur = view.model.images[0]
        assert view._histogram_cache[0] == cur
        assert view.requested == [view.model.images[1]]
        assert cur in view._filmstrip_thumb_cache

    def test_tile_wall_layers_paint(self, qapp, tmp_path):
        view = _tile_wall_view(tmp_path)
        assert _paint_each_layer(view) == [
            "draw_tile_overlays", "draw_tile_state_overlays",
            "draw_wall_loading", "draw_debug_hud", "draw_quick_meta_hud",
            "draw_tile_loupe",
        ]

    def test_loading_layers_paint(self, qapp, tmp_path):
        view = _loading_view(tmp_path)
        assert _paint_each_layer(view) == [
            "draw_loading_preview", "draw_filmstrip", "draw_debug_hud",
            "draw_quick_meta_hud", "draw_loading_pill", "draw_deep_zoom_error",
        ]

    @pytest.mark.parametrize("factory",
                             [_deep_zoom_view, _tile_wall_view, _loading_view])
    def test_paint_composites_without_layer_failures(
            self, qapp, tmp_path, monkeypatch, factory):
        failures = []
        real = op_mod._run_overlay_layers

        def _recording(p, layers):
            failed = real(p, layers)
            failures.extend(failed)
            return failed

        monkeypatch.setattr(op_mod, "_run_overlay_layers", _recording)
        image = _paint_whole_overlay(factory(tmp_path))
        assert failures == []
        assert _opaque_pixel_count(image) > 0

    def test_paint_with_no_layers_draws_nothing(self, qapp, tmp_path):
        view = _loading_view(tmp_path)
        view._deep_zoom_loading = None
        view._deep_zoom_error = None
        view._filmstrip_enabled = False
        view._show_debug_hud = False
        view._quick_meta_hud = None
        assert _opaque_pixel_count(_paint_whole_overlay(view)) == 0
