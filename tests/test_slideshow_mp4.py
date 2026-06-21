"""Tests for the MP4 slideshow generator.

MP4 writing requires ``imageio-ffmpeg`` which may not be installed in every
dev environment. Tests focus on the pure helpers plus error paths; the full
write path is exercised only when the dependency is available.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.export import slideshow_mp4 as sm


class TestSlideshowOptions:
    def test_defaults(self):
        opts = sm.SlideshowOptions()
        assert opts.width == 1920
        assert opts.height == 1080
        assert opts.fps == 24
        assert opts.hold_seconds == pytest.approx(3.0)
        assert opts.fade_seconds == pytest.approx(0.5)
        assert opts.quality == 8

    def test_is_frozen(self):
        import dataclasses
        opts = sm.SlideshowOptions()
        with pytest.raises(dataclasses.FrozenInstanceError):
            opts.fps = 60  # type: ignore[misc]


class TestFitToCanvas:
    def test_landscape_input_letterboxes_vertically(self):
        rgb = np.full((100, 200, 3), 128, dtype=np.uint8)
        out = sm._fit_to_canvas(rgb, 400, 400)
        assert out.shape == (400, 400, 3)
        # Top and bottom should be black padding.
        assert out[0].sum() == 0
        assert out[-1].sum() == 0
        # Centre row should be non-black.
        assert out[200].sum() > 0

    def test_portrait_input_letterboxes_horizontally(self):
        rgb = np.full((200, 100, 3), 128, dtype=np.uint8)
        out = sm._fit_to_canvas(rgb, 400, 400)
        assert out.shape == (400, 400, 3)
        assert out[:, 0].sum() == 0
        assert out[:, -1].sum() == 0

    def test_square_input_fills_canvas(self):
        rgb = np.full((100, 100, 3), 50, dtype=np.uint8)
        out = sm._fit_to_canvas(rgb, 200, 200)
        assert out.shape == (200, 200, 3)
        # Should have meaningful coverage in the middle.
        assert out[100, 100].sum() > 0

    def test_output_dtype_is_uint8(self):
        rgb = np.full((10, 10, 3), 128, dtype=np.uint8)
        out = sm._fit_to_canvas(rgb, 32, 32)
        assert out.dtype == np.uint8


class TestGenerateValidation:
    def test_empty_list_raises(self, tmp_path):
        with pytest.raises(ValueError, match="at least one image"):
            sm.generate_slideshow_mp4([], str(tmp_path / "out.mp4"))

    def test_missing_imageio_raises_runtime_error(self, tmp_path, monkeypatch):
        import sys
        # Block imageio.v2 even if installed.
        monkeypatch.setitem(sys.modules, "imageio.v2", None)
        with pytest.raises(RuntimeError, match="imageio"):
            sm.generate_slideshow_mp4(
                ["/does/not/exist.png"], str(tmp_path / "out.mp4"),
            )


class TestWriteSlide:
    def test_append_called_for_each_frame(self):
        calls: list[np.ndarray] = []

        class _FakeWriter:
            def append_data(self, frame):
                calls.append(frame)

        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        sm._write_slide(_FakeWriter(), frame, frames=5)
        assert len(calls) == 5


class TestWriteFade:
    def test_zero_frames_noop(self):
        calls: list[np.ndarray] = []

        class _FakeWriter:
            def append_data(self, frame):
                calls.append(frame)

        a = np.zeros((2, 2, 3), dtype=np.uint8)
        b = np.full((2, 2, 3), 255, dtype=np.uint8)
        sm._write_fade(_FakeWriter(), a, b, frames=0)
        assert calls == []

    def test_intermediate_frames_are_written(self):
        calls: list[np.ndarray] = []

        class _FakeWriter:
            def append_data(self, frame):
                calls.append(frame)

        a = np.zeros((2, 2, 3), dtype=np.uint8)
        b = np.full((2, 2, 3), 100, dtype=np.uint8)
        sm._write_fade(_FakeWriter(), a, b, frames=3)
        assert len(calls) == 3
        # Middle frame should be brighter than zero but dimmer than `b`.
        mid = calls[1]
        assert 0 < mid.mean() < 100
