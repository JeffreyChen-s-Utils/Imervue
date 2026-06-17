"""Tests for the shared video decode primitives (Imervue.image.video_frames)."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.image.video_frames import (
    VIDEO_EXTENSIONS,
    FrameReader,
    VideoBackendError,
    clamp_frame_index,
    frame_index_for_time,
    is_video_path,
    poster_frame,
    probe_video_meta,
    time_for_frame_index,
    to_rgb_uint8,
)


# ---------------------------------------------------------------------------
# clamp_frame_index
# ---------------------------------------------------------------------------


def test_clamp_within_range():
    assert clamp_frame_index(3, 10) == 3


def test_clamp_below_zero():
    assert clamp_frame_index(-5, 10) == 0


def test_clamp_above_max():
    assert clamp_frame_index(99, 10) == 9


def test_clamp_empty_stream():
    assert clamp_frame_index(4, 0) == 0
    assert clamp_frame_index(4, -1) == 0


# ---------------------------------------------------------------------------
# time <-> frame conversions
# ---------------------------------------------------------------------------


def test_frame_index_for_time_rounds_and_clamps():
    assert frame_index_for_time(1.0, 25.0, 100) == 25
    assert frame_index_for_time(0.49, 2.0, 100) == 1  # 0.98 -> round 1
    assert frame_index_for_time(1000.0, 25.0, 30) == 29  # clamped


def test_frame_index_for_time_guards_zero_fps():
    assert frame_index_for_time(5.0, 0.0, 100) == 0
    assert frame_index_for_time(5.0, -1.0, 100) == 0


def test_time_for_frame_index():
    assert time_for_frame_index(50, 25.0) == pytest.approx(2.0)
    assert time_for_frame_index(10, 0.0) == 0.0


# ---------------------------------------------------------------------------
# extension helpers
# ---------------------------------------------------------------------------


def test_is_video_path():
    assert is_video_path("movie.MP4") is True
    assert is_video_path("clip.mov") is True
    assert is_video_path("photo.png") is False


def test_known_extensions_present():
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".webm" in VIDEO_EXTENSIONS


# ---------------------------------------------------------------------------
# to_rgb_uint8
# ---------------------------------------------------------------------------


def test_to_rgb_passthrough():
    arr = np.zeros((4, 5, 3), dtype=np.uint8)
    out = to_rgb_uint8(arr)
    assert out.shape == (4, 5, 3)
    assert out.dtype == np.uint8


def test_to_rgb_from_grayscale():
    arr = np.arange(12, dtype=np.uint8).reshape(3, 4)
    out = to_rgb_uint8(arr)
    assert out.shape == (3, 4, 3)
    assert np.array_equal(out[..., 0], out[..., 2])


def test_to_rgb_drops_alpha():
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[..., 3] = 99
    out = to_rgb_uint8(arr)
    assert out.shape == (2, 2, 3)


def test_to_rgb_casts_non_uint8():
    arr = np.full((2, 2, 3), 300.0, dtype=np.float32)
    out = to_rgb_uint8(arr)
    assert out.dtype == np.uint8
    assert out.max() == 255


def test_to_rgb_rejects_bad_shape():
    with pytest.raises(ValueError):
        to_rgb_uint8(np.zeros((2, 2, 5), dtype=np.uint8))


# ---------------------------------------------------------------------------
# FrameReader / poster_frame — integration (needs imageio ffmpeg backend)
# ---------------------------------------------------------------------------


def _write_sample_video(path, frame_count=5):
    iio = pytest.importorskip("imageio").v2
    pytest.importorskip("imageio_ffmpeg")
    frames = [
        np.full((16, 16, 3), 40 + idx * 30, dtype=np.uint8)
        for idx in range(frame_count)
    ]
    try:
        iio.mimwrite(str(path), frames, format="ffmpeg", fps=5)
    except (OSError, RuntimeError, ValueError) as exc:  # ffmpeg binary issues
        pytest.skip(f"ffmpeg writer unavailable: {exc}")


def test_reader_info_and_frame(tmp_path):
    video = tmp_path / "clip.mp4"
    _write_sample_video(video)
    with FrameReader(str(video)) as reader:
        info = reader.info()
        assert info.frame_count >= 1
        assert info.width == 16
        assert info.height == 16
        arr = reader.frame(0)
        assert arr.shape == (16, 16, 3)
        assert arr.dtype == np.uint8


def test_poster_frame(tmp_path):
    video = tmp_path / "clip.mp4"
    _write_sample_video(video)
    arr = poster_frame(str(video))
    assert arr.shape == (16, 16, 3)
    assert arr.dtype == np.uint8


def test_probe_video_meta(tmp_path):
    video = tmp_path / "clip.mp4"
    _write_sample_video(video)
    meta = probe_video_meta(str(video))
    assert meta["width"] == 16
    assert meta["height"] == 16
    assert meta["fps"] > 0
    assert meta["duration_s"] > 0
    assert meta["codec"]


def test_open_missing_file_raises_backend_error():
    pytest.importorskip("imageio")
    pytest.importorskip("imageio_ffmpeg")
    with pytest.raises(VideoBackendError):
        FrameReader("definitely_missing_video.mp4").open()
