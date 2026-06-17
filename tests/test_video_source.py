"""Tests for the Video Source plugin (frame planning, extraction, dialog)."""
from __future__ import annotations

import numpy as np
import pytest

from video_source.video_frames import (
    DEFAULT_OUTPUT_EXT,
    FrameReader,
    VideoInfo,
    default_frame_dir,
    extract_frames,
    normalize_ext,
    output_frame_name,
    pil_format_for_ext,
    planned_frame_indices,
)


# ---------------------------------------------------------------------------
# planned_frame_indices
# ---------------------------------------------------------------------------


def test_plan_every_frame():
    assert planned_frame_indices(0, 4, 1, 5) == [0, 1, 2, 3, 4]


def test_plan_with_step_is_inclusive():
    assert planned_frame_indices(0, 9, 3, 10) == [0, 3, 6, 9]


def test_plan_clamps_range_to_stream():
    assert planned_frame_indices(-5, 999, 1, 3) == [0, 1, 2]


def test_plan_step_forced_to_minimum():
    assert planned_frame_indices(0, 2, 0, 3) == [0, 1, 2]
    assert planned_frame_indices(0, 2, -4, 3) == [0, 1, 2]


def test_plan_empty_stream_returns_empty():
    assert planned_frame_indices(0, 4, 1, 0) == []


def test_plan_inverted_range_returns_empty():
    assert planned_frame_indices(4, 1, 1, 10) == []


# ---------------------------------------------------------------------------
# naming + format helpers
# ---------------------------------------------------------------------------


def test_normalize_ext_adds_dot_and_lowercases():
    assert normalize_ext("PNG") == ".png"
    assert normalize_ext(".JPG") == ".jpg"


def test_normalize_ext_empty_falls_back():
    assert normalize_ext("") == DEFAULT_OUTPUT_EXT
    assert normalize_ext("   ") == DEFAULT_OUTPUT_EXT


def test_output_frame_name_is_zero_padded():
    assert output_frame_name("/a/b/clip.mp4", 7, "png") == "clip_frame000007.png"


def test_pil_format_for_ext():
    assert pil_format_for_ext(".jpg") == "JPEG"
    assert pil_format_for_ext(".jpeg") == "JPEG"
    assert pil_format_for_ext(".png") == "PNG"
    assert pil_format_for_ext(".unknown") == "PNG"


def test_default_frame_dir():
    assert default_frame_dir("/videos/clip.mp4").replace("\\", "/").endswith(
        "/videos/clip_frames",
    )


# ---------------------------------------------------------------------------
# extract_frames — integration (needs imageio ffmpeg backend)
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


def test_extract_frames_writes_files(tmp_path):
    video = tmp_path / "clip.mp4"
    _write_sample_video(video)
    with FrameReader(str(video)) as reader:
        frame_count = reader.info().frame_count
    indices = planned_frame_indices(0, frame_count - 1, 2, frame_count)
    out_dir = tmp_path / "out"
    saved = extract_frames(str(video), indices, str(out_dir), ext=".png")
    assert len(saved) == len(indices)
    assert all(path.exists() for path in saved)


# ---------------------------------------------------------------------------
# Qt smoke test — dialog wiring without a real video (injected fake reader)
# ---------------------------------------------------------------------------


class _FakeReader:
    """Stand-in for FrameReader that returns a flat frame for any index."""

    def __init__(self):
        self.requested: list[int] = []

    def frame(self, index: int) -> np.ndarray:
        self.requested.append(index)
        return np.full((16, 16, 3), 120, dtype=np.uint8)


def test_dialog_smoke(qapp):
    from video_source.video_source_plugin import VideoImportDialog

    info = VideoInfo("clip.mp4", frame_count=5, fps=25.0, duration_s=0.2,
                     width=16, height=16)
    reader = _FakeReader()
    dialog = VideoImportDialog(object(), "clip.mp4", reader, info)
    try:
        assert dialog._slider.maximum() == 4
        assert dialog._format.count() == 2
        assert dialog._out_dir.text().endswith("clip_frames")
        # Preview rendered frame 0 during construction.
        assert reader.requested == [0]
        assert not dialog._preview.pixmap().isNull()
    finally:
        dialog.deleteLater()
