"""
Tests for the crop tool — canvas crop state management and image cropping.

Imports PySide6 for AnnotationCanvas; requires the ``qapp`` fixture.
"""
from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QUndoStack

from Imervue.gui.annotation_dialog import AnnotationCanvas


@pytest.fixture
def white_image():
    """200x150 white RGBA image."""
    arr = np.full((150, 200, 4), 255, dtype=np.uint8)
    return Image.fromarray(arr, "RGBA")


@pytest.fixture
def canvas(qapp, white_image):
    stack = QUndoStack()
    c = AnnotationCanvas(white_image, stack)
    c.resize(400, 300)
    yield c


# ---------------------------------------------------------------------------
# Crop state management
# ---------------------------------------------------------------------------

class TestCropState:
    def test_initial_crop_is_none(self, canvas):
        assert canvas.get_crop_rect() is None

    def test_set_and_get_crop_rect(self, canvas):
        canvas._crop_rect = (10, 20, 100, 80)
        assert canvas.get_crop_rect() == (10, 20, 100, 80)

    def test_clear_crop(self, canvas):
        canvas._crop_rect = (10, 20, 100, 80)
        canvas.clear_crop()
        assert canvas.get_crop_rect() is None
        assert canvas._crop_dragging is False

    def test_set_crop_ratio_free(self, canvas):
        canvas._crop_rect = (10, 10, 100, 50)
        canvas.set_crop_ratio(0, 0)  # free
        # Should not change the rect
        assert canvas.get_crop_rect() == (10, 10, 100, 50)

    def test_set_crop_ratio_1_1(self, canvas):
        canvas._crop_rect = (10, 10, 100, 50)
        canvas.set_crop_ratio(1, 1)
        x, y, w, h = canvas.get_crop_rect()
        assert w == h, f"Expected square, got {w}x{h}"

    def test_set_crop_ratio_16_9(self, canvas):
        canvas._crop_rect = (0, 0, 160, 90)
        canvas.set_crop_ratio(16, 9)
        x, y, w, h = canvas.get_crop_rect()
        ratio = w / h
        assert abs(ratio - 16 / 9) < 0.1

    def test_enforce_ratio_clamps_to_image(self, canvas):
        """Crop rect should not exceed image bounds after ratio enforcement."""
        canvas._crop_rect = (180, 130, 100, 100)
        canvas.set_crop_ratio(1, 1)
        x, y, w, h = canvas.get_crop_rect()
        assert x >= 0 and y >= 0
        assert x + w <= 200 and y + h <= 150


# ---------------------------------------------------------------------------
# Crop tool mode
# ---------------------------------------------------------------------------

class TestCropToolMode:
    def test_set_tool_crop(self, canvas):
        canvas.set_tool("crop")
        assert canvas._tool == "crop"

    def test_set_tool_away_clears_crop(self, canvas):
        canvas._crop_rect = (10, 10, 50, 50)
        canvas.set_tool("crop")
        # Switching to select should clear crop (done by develop_panel)
        canvas.clear_crop()
        canvas.set_tool("select")
        assert canvas.get_crop_rect() is None


# ---------------------------------------------------------------------------
# Actual image crop (PIL)
# ---------------------------------------------------------------------------

class TestImageCrop:
    def test_pil_crop_produces_correct_size(self, white_image):
        cropped = white_image.crop((10, 20, 110, 100))
        assert cropped.size == (100, 80)

    def test_crop_saves_to_file(self, white_image, tmp_path):
        """Simulate the crop-and-save flow used by DevelopPanel._apply_crop."""
        # Draw a red rectangle on the image so we can verify the crop
        arr = np.array(white_image)
        arr[30:60, 40:80] = [255, 0, 0, 255]
        img = Image.fromarray(arr, "RGBA")

        # Crop to the red region
        cropped = img.crop((40, 30, 80, 60))
        assert cropped.size == (40, 30)

        # Save
        path = tmp_path / "cropped.png"
        cropped.save(str(path), format="PNG")
        assert path.exists()

        # Reload and verify
        reloaded = Image.open(str(path))
        arr_out = np.array(reloaded.convert("RGBA"))
        # Center pixel should be red
        assert arr_out[15, 20, 0] == 255
        assert arr_out[15, 20, 1] == 0

    def test_crop_jpeg_converts_rgba(self, tmp_path):
        """JPEG does not support alpha — crop should handle conversion."""
        arr = np.full((100, 100, 4), 200, dtype=np.uint8)
        img = Image.fromarray(arr, "RGBA")
        cropped = img.crop((10, 10, 60, 60))
        path = tmp_path / "cropped.jpg"
        save_img = cropped.convert("RGB")
        save_img.save(str(path), format="JPEG")
        assert path.exists()
        reloaded = Image.open(str(path))
        assert reloaded.mode == "RGB"
        assert reloaded.size == (50, 50)


# ---------------------------------------------------------------------------
# Crop UI placement (right panel)
# ---------------------------------------------------------------------------

class TestCropWidgetPlacement:
    """Verify the crop controls are built in the right panel with adequate width."""

    @pytest.fixture
    def develop_panel(self, qapp, white_image):
        from unittest.mock import MagicMock
        from PySide6.QtWidgets import QSplitter
        main_gui = MagicMock()
        from Imervue.gui.develop_panel import DevelopPanel
        dp = DevelopPanel(main_gui)
        splitter = QSplitter()
        dp.build_left_panel(splitter)
        dp.build_right_panel(splitter)
        dp._test_splitter = splitter  # prevent GC
        return dp

    def test_crop_widget_exists(self, develop_panel):
        assert hasattr(develop_panel, '_crop_widget')
        assert hasattr(develop_panel, '_crop_ratio_combo')
        assert hasattr(develop_panel, '_crop_apply_btn')
        assert hasattr(develop_panel, '_crop_cancel_btn')

    def test_crop_widget_hidden_by_default(self, develop_panel):
        assert not develop_panel._crop_widget.isVisible()

    def test_crop_widget_in_right_panel(self, develop_panel):
        """Crop widget should be parented under the right panel, not the left."""
        parent = develop_panel._crop_widget.parentWidget()
        # The right panel inner widget has the color button, sliders, etc.
        # Verify the crop widget shares a parent with the color button.
        assert parent is develop_panel._color_btn.parentWidget()
