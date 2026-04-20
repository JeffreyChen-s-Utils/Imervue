"""Tests for the animated-image (GIF / APNG / animated WebP) player."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.actions import animation_player as ap


def _make_static_png(path):
    Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(path))
    return str(path)


def _make_gif(path, n_frames: int = 3):
    frames = []
    for i in range(n_frames):
        arr = np.full((8, 8, 3), i * 60, dtype=np.uint8)
        frames.append(Image.fromarray(arr))
    frames[0].save(
        str(path), save_all=True, append_images=frames[1:],
        duration=50, loop=0,
    )
    return str(path)


class _FakeGui:
    """Minimal stand-in that satisfies AnimationPlayer._apply_frame."""

    def __init__(self):
        self.deep_zoom = None
        self.tile_manager = None
        self._histogram_cache = object()
        self.updates = 0

    def update(self):
        self.updates += 1


class TestIsAnimatedFile:
    def test_true_for_multiframe_gif(self, tmp_path):
        p = _make_gif(tmp_path / "anim.gif", n_frames=4)
        assert ap.is_animated_file(p) is True

    def test_false_for_single_frame_png(self, tmp_path):
        p = _make_static_png(tmp_path / "still.png")
        assert ap.is_animated_file(p) is False

    def test_false_for_unsupported_extension(self, tmp_path):
        p = tmp_path / "photo.jpg"
        Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(p), "JPEG")
        assert ap.is_animated_file(str(p)) is False

    def test_false_for_unreadable_file(self, tmp_path):
        p = tmp_path / "broken.gif"
        p.write_bytes(b"not a gif")
        assert ap.is_animated_file(str(p)) is False


class TestLoad:
    def test_static_file_returns_false(self, tmp_path, qapp):
        p = _make_static_png(tmp_path / "still.png")
        player = ap.AnimationPlayer(_FakeGui(), p)
        assert player.load() is False
        assert player.total_frames == 0

    def test_multiframe_gif_loads_all_frames(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "anim.gif", n_frames=5)
        player = ap.AnimationPlayer(_FakeGui(), p)
        assert player.load() is True
        assert player.total_frames == 5
        assert player.is_animated is True
        assert all(len(d) > 0 for d in [player.durations])

    def test_missing_file_returns_false(self, tmp_path, qapp):
        player = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "ghost.gif"))
        assert player.load() is False


class TestFrameNavigation:
    @pytest.fixture
    def player(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "anim.gif", n_frames=4)
        pl = ap.AnimationPlayer(_FakeGui(), p)
        pl.load()
        return pl

    def test_next_frame_advances(self, player):
        player.next_frame()
        assert player.current_frame == 1

    def test_next_frame_wraps_around(self, player):
        player.go_to_frame(player.total_frames - 1)
        player.next_frame()
        assert player.current_frame == 0

    def test_prev_frame_wraps_backward(self, player):
        player.prev_frame()
        assert player.current_frame == player.total_frames - 1

    def test_go_to_frame_clamps(self, player):
        player.go_to_frame(99)
        assert player.current_frame == player.total_frames - 1
        player.go_to_frame(-10)
        assert player.current_frame == 0

    def test_navigation_noops_when_static(self, tmp_path, qapp):
        p = _make_static_png(tmp_path / "still.png")
        pl = ap.AnimationPlayer(_FakeGui(), p)
        # Static images don't load frames.
        pl.load()
        pl.next_frame()
        pl.prev_frame()
        assert pl.current_frame == 0


class TestPlayPause:
    def test_toggle_flips_state(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "anim.gif")
        pl = ap.AnimationPlayer(_FakeGui(), p)
        pl.load()
        assert pl.playing is False
        pl.toggle()
        assert pl.playing is True
        pl.toggle()
        assert pl.playing is False

    def test_play_noop_when_static(self, tmp_path, qapp):
        p = _make_static_png(tmp_path / "still.png")
        pl = ap.AnimationPlayer(_FakeGui(), p)
        pl.play()
        assert pl.playing is False


class TestSpeedClamping:
    def test_speed_clamped_low(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "x.gif"))
        pl.set_speed(0.01)
        assert pl.speed == 0.25

    def test_speed_clamped_high(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "x.gif"))
        pl.set_speed(100.0)
        assert pl.speed == 4.0

    def test_speed_in_range_preserved(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "x.gif"))
        pl.set_speed(2.0)
        assert pl.speed == 2.0


class TestFrameData:
    def test_empty_when_not_loaded(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "ghost.gif"))
        assert pl.get_current_frame_data() is None

    def test_returns_rgba_uint8(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "anim.gif")
        pl = ap.AnimationPlayer(_FakeGui(), p)
        pl.load()
        arr = pl.get_current_frame_data()
        assert arr is not None
        assert arr.shape[2] == 4
        assert arr.dtype == np.uint8


class TestStop:
    def test_clears_frames_and_state(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "anim.gif")
        pl = ap.AnimationPlayer(_FakeGui(), p)
        pl.load()
        pl.stop()
        assert pl.frames == []
        assert pl.durations == []
        assert pl.playing is False


class TestAnimatedExts:
    def test_covers_common_formats(self):
        assert ap.ANIMATED_EXTS >= {".gif", ".apng", ".webp", ".png"}
