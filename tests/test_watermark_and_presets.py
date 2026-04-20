"""Tests for watermark compositing and export presets."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def wm():
    from Imervue.image import watermark
    return watermark


@pytest.fixture
def presets():
    from Imervue.image import export_presets
    return export_presets


@pytest.fixture
def blue_image() -> Image.Image:
    arr = np.zeros((200, 300, 3), dtype=np.uint8)
    arr[..., 2] = 255  # solid blue
    return Image.fromarray(arr)


class TestWatermarkOptions:
    def test_is_active_empty_text(self, wm):
        assert wm.WatermarkOptions().is_active() is False

    def test_is_active_whitespace_only(self, wm):
        assert wm.WatermarkOptions(text="   ").is_active() is False

    def test_is_active_with_text(self, wm):
        assert wm.WatermarkOptions(text="\u00a9 Me").is_active() is True


class TestApplyWatermark:
    def test_no_text_returns_same_size(self, wm, blue_image):
        out = wm.apply_watermark(blue_image, wm.WatermarkOptions())
        assert out.size == blue_image.size

    def test_with_text_changes_pixels(self, wm, blue_image):
        opts = wm.WatermarkOptions(text="HELLO", corner="bottom-right")
        out = wm.apply_watermark(blue_image, opts)
        # Bottom-right region should differ now that text is drawn there
        src_arr = np.array(blue_image.convert("RGBA"))
        out_arr = np.array(out.convert("RGBA"))
        h, w = out_arr.shape[:2]
        br_src = src_arr[h * 2 // 3:, w * 2 // 3:]
        br_out = out_arr[h * 2 // 3:, w * 2 // 3:]
        assert not np.array_equal(br_src, br_out)

    def test_invalid_corner_falls_back_to_bottom_right(self, wm, blue_image):
        opts = wm.WatermarkOptions(text="X", corner="not-a-corner")
        # Should not raise; returns same-size image
        out = wm.apply_watermark(blue_image, opts)
        assert out.size == blue_image.size

    def test_output_has_alpha_mode(self, wm, blue_image):
        opts = wm.WatermarkOptions(text="A")
        out = wm.apply_watermark(blue_image, opts)
        assert out.mode == "RGBA"


class TestExportPresets:
    def test_builtin_presets_nonempty(self, presets):
        assert len(presets.builtin_presets()) >= 5

    def test_preset_keys_unique(self, presets):
        keys = [p.key for p in presets.builtin_presets()]
        assert len(keys) == len(set(keys))

    def test_get_preset_web_1600(self, presets):
        p = presets.get_preset("web_1600")
        assert p is not None
        assert p.format == "JPEG"
        assert p.max_width == 1600
        assert p.max_height == 1600

    def test_get_preset_instagram_is_square(self, presets):
        p = presets.get_preset("instagram_1080")
        assert p is not None
        assert p.square_crop is True
        assert p.max_width == 1080 == p.max_height

    def test_get_preset_print_has_dpi(self, presets):
        p = presets.get_preset("print_300dpi")
        assert p is not None
        assert p.dpi == 300

    def test_get_preset_unknown_returns_none(self, presets):
        assert presets.get_preset("does-not-exist") is None

    def test_square_crop_produces_square(self, presets):
        img = Image.new("RGB", (400, 200), (0, 0, 0))
        cropped = presets.square_crop(img)
        assert cropped.size == (200, 200)

    def test_square_crop_wide_centered(self, presets):
        img = Image.new("RGB", (300, 200), (0, 0, 0))
        cropped = presets.square_crop(img)
        assert cropped.size == (200, 200)

    def test_square_crop_tall_centered(self, presets):
        img = Image.new("RGB", (100, 300), (0, 0, 0))
        cropped = presets.square_crop(img)
        assert cropped.size == (100, 100)
