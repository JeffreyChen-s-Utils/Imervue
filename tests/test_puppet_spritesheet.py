"""Tests for the puppet spritesheet composer (pure numpy, no Qt/GL)."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.puppet.spritesheet import (
    compose_spritesheet,
    grid_dimensions,
    save_spritesheet,
)


def _frame(value, h=2, w=3, c=4):
    return np.full((h, w, c), value, dtype=np.uint8)


class TestGridDimensions:
    @pytest.mark.parametrize("n,max_cols,expected", [
        (0, 8, (0, 0)),
        (1, 8, (1, 1)),
        (5, 8, (5, 1)),
        (8, 8, (8, 1)),
        (9, 8, (8, 2)),
        (16, 4, (4, 4)),
        (7, 3, (3, 3)),
    ])
    def test_grid(self, n, max_cols, expected):
        assert grid_dimensions(n, max_cols) == expected

    def test_max_cols_below_one_is_treated_as_one(self):
        assert grid_dimensions(3, 0) == (1, 3)


class TestComposeSpritesheet:
    def test_tiles_frames_row_major(self):
        frames = [_frame(i) for i in range(4)]
        sheet = compose_spritesheet(frames, cols=2)
        assert sheet.shape == (4, 6, 4)
        assert sheet[0, 0, 0] == 0    # frame 0 → row 0, col 0
        assert sheet[0, 3, 0] == 1    # frame 1 → row 0, col 1
        assert sheet[2, 0, 0] == 2    # frame 2 → row 1, col 0
        assert sheet[2, 3, 0] == 3    # frame 3 → row 1, col 1

    def test_unfilled_cells_stay_zero(self):
        sheet = compose_spritesheet([_frame(9) for _ in range(3)], cols=2)
        assert sheet.shape == (4, 6, 4)
        assert sheet[2, 3, 0] == 0  # 4th cell has no frame

    def test_grayscale_frames_get_a_channel_axis(self):
        sheet = compose_spritesheet([np.full((2, 3), 5, dtype=np.uint8)], cols=1)
        assert sheet.shape == (2, 3, 1)
        assert sheet[0, 0, 0] == 5

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="at least one frame"):
            compose_spritesheet([], cols=2)

    def test_non_positive_cols_raises(self):
        with pytest.raises(ValueError, match="cols must be positive"):
            compose_spritesheet([_frame(1)], cols=0)

    def test_mismatched_shapes_raise(self):
        with pytest.raises(ValueError, match="same shape"):
            compose_spritesheet([_frame(1, w=3), _frame(2, w=5)], cols=2)


class TestSaveSpritesheet:
    def test_round_trip_rgba(self, tmp_path):
        out = tmp_path / "sheet.png"
        cols, rows = save_spritesheet([_frame(i) for i in range(4)], out)
        assert (cols, rows) == (4, 1)
        with Image.open(out) as im:
            # 4 frames of 3x2 in a 4x1 grid → 12 wide, 2 tall.
            assert im.size == (12, 2)

    def test_round_trip_grayscale(self, tmp_path):
        out = tmp_path / "gray.png"
        frames = [np.full((2, 3), v, dtype=np.uint8) for v in (10, 20)]
        save_spritesheet(frames, out, max_cols=2)
        with Image.open(out) as im:
            assert im.size == (6, 2)
            assert im.mode == "L"


class TestSaveSpritesheetFromQimages:
    """The recorder bridge needs QImage (qapp) but no QOpenGLWidget."""

    def test_packs_qimage_frames(self, qapp, tmp_path):
        from PySide6.QtGui import QColor, QImage

        from Imervue.puppet.recorder import save_spritesheet_from_qimages
        frames = []
        for value in (10, 20, 30, 40):
            img = QImage(3, 2, QImage.Format.Format_RGB888)
            img.fill(QColor(value, value, value))
            frames.append(img)
        cols, rows = save_spritesheet_from_qimages(frames, tmp_path / "rec.png")
        assert (cols, rows) == (4, 1)
        with Image.open(tmp_path / "rec.png") as im:
            assert im.size == (12, 2)

    def test_no_frames_raises(self, qapp, tmp_path):
        from Imervue.puppet.recorder import save_spritesheet_from_qimages
        with pytest.raises(ValueError, match="no convertible frames"):
            save_spritesheet_from_qimages([], tmp_path / "x.png")
