"""Tests for drag-out helpers."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap

from Imervue.gpu_image_view.actions import drag_out


@pytest.fixture
def sample_png(tmp_path):
    p = tmp_path / "img.png"
    Image.fromarray(np.zeros((32, 48, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class _FakeGui:
    def __init__(self, tile_grid_mode=True, tiles=None, selected=None):
        self.tile_grid_mode = tile_grid_mode
        self.tile_rects = tiles or []
        self.selected_tiles = set(selected or ())


class TestBuildPreviewPixmap:
    def test_returns_pixmap_for_valid_image(self, sample_png, qapp):
        px = drag_out._build_preview_pixmap(_FakeGui(), sample_png)
        assert isinstance(px, QPixmap)
        assert not px.isNull()

    def test_returns_none_for_broken_file(self, tmp_path, qapp):
        bad = tmp_path / "broken.png"
        bad.write_bytes(b"not a real png")
        assert drag_out._build_preview_pixmap(_FakeGui(), str(bad)) is None

    def test_returns_none_for_missing_file(self, tmp_path, qapp):
        assert drag_out._build_preview_pixmap(
            _FakeGui(), str(tmp_path / "ghost.png"),
        ) is None

    def test_scales_to_96_max_side(self, tmp_path, qapp):
        # Large source should be scaled down to at most 96 on the long edge.
        big = tmp_path / "big.png"
        Image.fromarray(np.zeros((200, 300, 3), dtype=np.uint8)).save(str(big))
        px = drag_out._build_preview_pixmap(_FakeGui(), str(big))
        assert px is not None
        assert max(px.width(), px.height()) <= 96


class TestTryStartDragOutGuards:
    def test_returns_false_when_not_tile_mode(self, qapp):
        gui = _FakeGui(tile_grid_mode=False)
        assert drag_out.try_start_drag_out(gui, QPoint(10, 10)) is False

    def test_returns_false_when_no_tile_under_cursor(self, qapp):
        gui = _FakeGui(
            tiles=[(0, 0, 50, 50, "/p/a.jpg")],
            selected={"/p/a.jpg"},
        )
        # Press outside all tile rects.
        assert drag_out.try_start_drag_out(gui, QPoint(999, 999)) is False

    def test_returns_false_when_tile_not_selected(self, qapp):
        gui = _FakeGui(
            tiles=[(0, 0, 50, 50, "/p/a.jpg")],
            selected=set(),  # Nothing selected.
        )
        assert drag_out.try_start_drag_out(gui, QPoint(10, 10)) is False


class TestDoDragUriFiltering:
    """_do_drag refuses to start when no URL passes the is_file filter."""

    def test_returns_false_when_no_paths_exist(self, qapp):
        gui = _FakeGui()
        assert drag_out._do_drag(gui, ["/does/not/exist.png"]) is False
