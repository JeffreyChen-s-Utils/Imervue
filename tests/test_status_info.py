"""Tests for status_info — main-window status-bar field building."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from Imervue.gpu_image_view import status_info


class _RecordingMW:
    def __init__(self):
        self.last = None
        self.cleared = False

    def update_status_info(self, **kw):
        self.last = kw

    def clear_status_info(self):
        self.cleared = True


class _FakeDeepZoom:
    def __init__(self, w, h):
        self.levels = [np.zeros((h, w, 4), dtype=np.uint8)]


def _view(mw, **kw):
    base = {
        "main_window": mw,
        "model": SimpleNamespace(images=[]),
        "current_index": 0,
        "deep_zoom": None,
        "zoom": 1.0,
        "_hover_image_xy": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_no_status_method_is_noop():
    view = _view(SimpleNamespace())  # no update_status_info attr
    status_info.update_status_info(view)  # must not raise


def test_no_images_clears_status():
    mw = _RecordingMW()
    status_info.update_status_info(_view(mw))
    assert mw.cleared is True


def test_tile_grid_index_placeholder():
    mw = _RecordingMW()
    view = _view(mw, model=SimpleNamespace(images=["a", "b", "c"]))
    status_info.update_status_info(view)
    # No deep zoom → "— / N" form.
    assert mw.last["index"] == "— / 3"
    assert mw.last["zoom"] == ""


def test_deep_zoom_full_fields(monkeypatch):
    mw = _RecordingMW()
    view = _view(
        mw,
        model=SimpleNamespace(images=["a.png", "b.png"]),
        current_index=1,
        deep_zoom=_FakeDeepZoom(800, 600),
        zoom=0.5,
        _hover_image_xy=(100, 50),
    )
    monkeypatch.setattr(
        "Imervue.user_settings.color_labels.get_color_label", lambda p: "red"
    )
    monkeypatch.setattr(status_info, "_format_file_size", lambda p: "1.0 KB")
    status_info.update_status_info(view)
    assert mw.last["index"] == "2/2"
    assert mw.last["resolution"] == "800×600"
    assert mw.last["zoom"] == "50%"
    assert mw.last["cursor"] == "x=100, y=50"
    assert mw.last["label"] == "red"


def test_cursor_outside_image_is_blank():
    view = _view(
        _RecordingMW(),
        deep_zoom=_FakeDeepZoom(100, 100),
        _hover_image_xy=(500, 500),
    )
    assert status_info._format_cursor(view, 100, 100) == ""


def test_cursor_none_is_blank():
    view = _view(_RecordingMW(), _hover_image_xy=None)
    assert status_info._format_cursor(view, 100, 100) == ""


def test_format_file_size_missing_file_is_blank():
    assert status_info._format_file_size("/no/such/file.xyz") == ""
