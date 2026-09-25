"""Tests for the animated-image (GIF / APNG / animated WebP) player."""
from __future__ import annotations

import contextlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.gpu_image_view.actions import animation_player as ap
from Imervue.gpu_image_view.actions.animation_player import can_cache_pyramid


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

    def _current_gl_context(self):
        return contextlib.nullcontext()

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
        assert pl.speed == pytest.approx(0.25)

    def test_speed_clamped_high(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "x.gif"))
        pl.set_speed(100.0)
        assert pl.speed == pytest.approx(4.0)

    def test_speed_in_range_preserved(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), str(tmp_path / "x.gif"))
        pl.set_speed(2.0)
        assert pl.speed == pytest.approx(2.0)


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
        assert {".gif", ".apng", ".webp", ".png"} <= ap.ANIMATED_EXTS


class TestPyramidMemoization:
    def test_can_cache_pyramid_budget(self):
        assert can_cache_pyramid(0, 999, 100) is True   # first entry always fits
        assert can_cache_pyramid(50, 40, 100) is True    # 90 <= 100
        assert can_cache_pyramid(80, 40, 100) is False   # 120 > 100

    def test_apply_frame_reuses_cached_pyramid_on_replay(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "a.gif", n_frames=3)
        gui = _FakeGui()
        gui.deep_zoom = object()  # non-None so _apply_frame proceeds
        pl = ap.AnimationPlayer(gui, p)
        pl.load()
        pl.go_to_frame(0)
        first = gui.deep_zoom
        pl.go_to_frame(1)
        assert gui.deep_zoom is not first          # different frame → rebuilt
        pl.go_to_frame(0)
        assert gui.deep_zoom is first              # replayed → cached pyramid

    def test_apply_frame_frees_old_tiles_inside_gl_context(self, tmp_path, qapp):
        events: list = []

        class _Ctx:
            def __enter__(self):
                events.append("enter")
                return self

            def __exit__(self, *_a):
                events.append("exit")
                return False

        class _TM:
            def clear(self):
                events.append("clear")

        p = _make_gif(tmp_path / "a.gif", n_frames=2)
        gui = _FakeGui()
        gui.deep_zoom = object()
        gui.tile_manager = _TM()
        gui._current_gl_context = lambda: _Ctx()
        pl = ap.AnimationPlayer(gui, p)
        pl.load()
        pl.go_to_frame(1)
        assert events == ["enter", "clear", "exit"]  # freed in-context

    def test_stop_clears_pyramid_cache(self, tmp_path, qapp):
        p = _make_gif(tmp_path / "a.gif", n_frames=3)
        gui = _FakeGui()
        gui.deep_zoom = object()
        pl = ap.AnimationPlayer(gui, p)
        pl.load()
        pl.go_to_frame(0)
        assert pl._pyramid_cache            # populated
        pl.stop()
        assert pl._pyramid_cache == {}
        assert pl._pyramid_bytes == 0


class TestLoadFailures:
    def test_truncated_gif_keeps_the_frames_that_decode(self, tmp_path, qapp):
        full = _make_gif(tmp_path / "anim.gif", n_frames=4)
        data = Path(full).read_bytes()
        cut = tmp_path / "cut.gif"
        cut.write_bytes(data[: len(data) * 3 // 4])
        player = ap.AnimationPlayer(_FakeGui(), str(cut))
        loaded = player.load()
        assert player.total_frames < 4
        assert loaded is (player.total_frames > 1)

    def test_load_releases_the_file(self, tmp_path, qapp):
        import os
        p = _make_gif(tmp_path / "anim.gif", n_frames=3)
        assert ap.AnimationPlayer(_FakeGui(), p).load() is True
        assert ap.is_animated_file(p) is True
        os.remove(p)  # fails on Windows while a handle is still open

    def test_unexpected_open_error_propagates(self, tmp_path, qapp, monkeypatch):
        def boom(_path):
            raise RuntimeError("bug")

        monkeypatch.setattr(ap.Image, "open", boom)
        with pytest.raises(RuntimeError):
            ap.AnimationPlayer(_FakeGui(), str(tmp_path / "a.gif")).load()
        with pytest.raises(RuntimeError):
            ap.is_animated_file(str(tmp_path / "a.gif"))


def _make_timed_gif(path, durations):
    frames = [Image.fromarray(np.full((8, 8, 3), i * 40, dtype=np.uint8))
              for i in range(len(durations))]
    frames[0].save(str(path), save_all=True, append_images=frames[1:],
                   duration=list(durations), loop=0)
    return str(path)


class TestFrameDuration:
    @pytest.mark.parametrize(("info", "expected"), [
        ({"duration": 70}, 70), ({"duration": 0}, 100), ({"duration": None}, 100), ({}, 100),
    ])
    def test_missing_or_non_positive_plays_as_100_ms(self, info, expected):
        assert ap._frame_duration(info) == expected

    @pytest.mark.parametrize(("info", "expected"), [
        ({"duration": 10}, 100), ({"duration": 1}, 100), ({"duration": 10.0}, 100),
        ({"duration": 11}, 11), ({"duration": 20}, 20),
    ])
    def test_ten_ms_or_less_plays_as_100_ms_like_browsers(self, info, expected):
        """A GIF of 1-centisecond frames ran ten times faster here than in a browser."""
        assert ap._frame_duration(info) == expected


class TestStreamingLargeAnimations:
    """Past the decoded-frames budget, frames decode one at a time as they are shown."""

    @pytest.fixture
    def tiny_budget(self, monkeypatch):
        monkeypatch.setattr(ap, "_DECODED_FRAMES_BUDGET", 8 * 8 * 4 * 2)   # two 8x8 frames

    def test_an_animation_over_the_budget_streams(self, tmp_path, qapp, tiny_budget):
        pl = ap.AnimationPlayer(_FakeGui(), _make_gif(tmp_path / "big.gif", n_frames=5))
        assert pl.load() is True
        assert pl.streaming
        assert pl.frames == []
        assert pl.total_frames == 5

    def test_one_within_the_budget_is_decoded_up_front(self, tmp_path, qapp):
        pl = ap.AnimationPlayer(_FakeGui(), _make_gif(tmp_path / "small.gif", n_frames=5))
        pl.load()
        assert not pl.streaming
        assert len(pl.frames) == 5

    def test_streamed_frames_match_decoded_ones(self, tmp_path, qapp, monkeypatch):
        path = _make_gif(tmp_path / "anim.gif", n_frames=5)
        whole = ap.AnimationPlayer(_FakeGui(), path)
        whole.load()
        monkeypatch.setattr(ap, "_DECODED_FRAMES_BUDGET", 1)
        streamed = ap.AnimationPlayer(_FakeGui(), path)
        streamed.load()
        for index in (0, 1, 4, 3, 0, 2):                 # forward, back, around
            streamed.go_to_frame(index)
            assert np.array_equal(streamed.get_current_frame_data(), whole.frames[index])
        streamed.go_to_frame(0)
        streamed.prev_frame()
        assert streamed.current_frame == 4
        assert np.array_equal(streamed.get_current_frame_data(), whole.frames[4])

    def test_durations_fill_in_as_frames_are_shown(self, tmp_path, qapp, tiny_budget):
        pl = ap.AnimationPlayer(_FakeGui(), _make_timed_gif(tmp_path / "t.gif", [50, 120, 30]))
        pl.load()
        assert pl.durations == [50, 100, 100]
        pl.go_to_frame(1)
        pl.go_to_frame(2)
        assert pl.durations == [50, 120, 30]

    def test_the_file_is_not_held_open(self, tmp_path, qapp, tiny_budget):
        """Windows can't delete or rename a file an open handle holds."""
        path = Path(_make_gif(tmp_path / "anim.gif", n_frames=5))
        pl = ap.AnimationPlayer(_FakeGui(), str(path))
        pl.load()
        path.unlink()
        pl.go_to_frame(3)
        assert pl.get_current_frame_data() is not None

    def test_a_frame_that_fails_to_decode_keeps_the_last_one(self, tmp_path, qapp, tiny_budget,
                                                             monkeypatch):
        pl = ap.AnimationPlayer(_FakeGui(), _make_gif(tmp_path / "anim.gif", n_frames=5))
        pl.load()
        first = pl.get_current_frame_data()

        def broken(_index):
            raise OSError("truncated")

        monkeypatch.setattr(pl._source, "seek", broken)  # noqa: SLF001
        pl.go_to_frame(2)
        assert pl.get_current_frame_data() is first

    def test_stop_lets_go_of_the_stream(self, tmp_path, qapp, tiny_budget):
        pl = ap.AnimationPlayer(_FakeGui(), _make_gif(tmp_path / "anim.gif", n_frames=5))
        pl.load()
        pl.stop()
        assert not pl.streaming
        assert pl.total_frames == 0
        assert pl.get_current_frame_data() is None


class TestFramesThatAreNotAnAnimation:
    """Pillow reports frames for files whose extra frames must never play."""

    @staticmethod
    def _tiff(path, pages=3):
        images = [Image.new("RGB", (8, 6), colour) for colour in ("red", "green", "blue")[:pages]]
        images[0].save(str(path), save_all=True, append_images=images[1:])
        return str(path)

    def test_a_camera_jpegs_mpf_preview_is_not_a_second_frame(self, tmp_path, qapp):
        """A JPEG carrying an MPF preview opens as MPO: it flipped to the preview every 100 ms."""
        path = tmp_path / "DSC_0001.JPG"
        Image.new("RGB", (40, 30), "red").save(
            str(path), format="MPO", save_all=True, append_images=[Image.new("RGB", (20, 15), "gray")])
        with Image.open(path) as img:
            assert img.format == "MPO" and img.n_frames == 2
        player = ap.AnimationPlayer(None, str(path))
        assert player.load() is False
        assert not player.is_animated

    def test_a_multi_page_tiff_is_paged_not_played(self, tmp_path, qapp):
        """A scanned document flipped its pages at ten a second."""
        player = ap.AnimationPlayer(_FakeGui(), self._tiff(tmp_path / "scan.tif"))
        assert player.load() is True
        assert player.paged and player.total_frames == 3
        player.play()
        assert player.playing is False
        player.toggle()
        assert player.playing is False
        player.next_frame()
        assert player.current_frame == 1
        assert player.get_current_frame_data()[0, 0].tolist() == [0, 128, 0, 255]

    def test_a_gif_still_plays(self, tmp_path, qapp):
        player = ap.AnimationPlayer(_FakeGui(), _make_gif(tmp_path / "a.gif"))
        assert player.load() is True
        assert not player.paged
        player.play()
        assert player.playing is True
        player.pause()

    def test_sixteen_bit_pages_are_scaled_like_a_still(self, tmp_path, qapp):
        path = tmp_path / "scan16.tif"
        pages = [Image.fromarray(np.full((4, 4), value, dtype=np.uint16)) for value in (0, 32768, 65535)]
        pages[0].save(str(path), save_all=True, append_images=pages[1:])
        player = ap.AnimationPlayer(_FakeGui(), str(path))
        assert player.load() is True
        assert [int(frame[0, 0, 0]) for frame in player.frames] == [0, 128, 255]


class TestIndicatorText:
    @staticmethod
    def _anim(**fields):
        from types import SimpleNamespace
        defaults = {"current_frame": 1, "total_frames": 5, "paged": False, "playing": True, "speed": 1.0}
        return SimpleNamespace(**{**defaults, **fields})

    def test_a_document_shows_its_page(self):
        assert ap.anim_indicator_text(self._anim(paged=True), {}) == "Page 2/5"

    def test_an_animation_shows_state_frame_and_speed(self):
        assert ap.anim_indicator_text(self._anim(), {}) == "Pause  |  Frame 2/5  |  Speed: 1.0x"
        assert ap.anim_indicator_text(self._anim(playing=False), {}).startswith("Play  |")

    def test_the_page_readout_is_translated(self):
        from Imervue.multi_language.traditional_chinese import traditional_chinese_word_dict
        text = ap.anim_indicator_text(self._anim(paged=True), traditional_chinese_word_dict)
        assert text == "第 2/5 頁"


# --- An APNG's default image ----------------------------------------------------------------

_APNG_FRAMES = ((255, 0, 0), (0, 255, 0), (0, 0, 255))


def _make_apng(path, *, default_image: bool) -> str:
    """White default image, then red / green / blue animation frames of 40 / 50 / 60 ms."""
    frames = [Image.new("RGB", (8, 8), colour) for colour in _APNG_FRAMES]
    if default_image:
        Image.new("RGB", (8, 8), "white").save(
            path, save_all=True, append_images=frames, default_image=True, duration=[40, 50, 60], loop=0)
    else:
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[40, 50, 60], loop=0)
    return str(path)


def _colours(player) -> list[tuple[int, ...]]:
    out = []
    for index in range(player.total_frames):
        player.current_frame = index
        out.append(tuple(int(v) for v in player.get_current_frame_data()[0, 0, :3]))
    return out


class TestApngDefaultImage:
    """The picture shown to programs without APNG support is not an animation frame."""

    def test_the_default_image_is_left_out_of_the_animation(self, tmp_path):
        pl = ap.AnimationPlayer(_FakeGui(), _make_apng(tmp_path / "a.png", default_image=True))
        assert pl.load() is True
        assert pl.total_frames == 3
        assert _colours(pl) == list(_APNG_FRAMES)
        assert pl.durations == [40, 50, 60]

    def test_an_apng_whose_first_frame_is_its_image_keeps_it(self, tmp_path):
        pl = ap.AnimationPlayer(_FakeGui(), _make_apng(tmp_path / "a.png", default_image=False))
        assert pl.load() is True
        assert _colours(pl) == list(_APNG_FRAMES)

    def test_a_streamed_animation_leaves_it_out_too(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ap, "_DECODED_FRAMES_BUDGET", 1)
        pl = ap.AnimationPlayer(_FakeGui(), _make_apng(tmp_path / "a.png", default_image=True))
        assert pl.load() is True
        assert pl.streaming and pl.total_frames == 3
        assert _colours(pl) == list(_APNG_FRAMES)
        assert pl.durations[0] == 40

    def test_the_first_frame_replaces_the_default_image_on_screen(self, tmp_path, monkeypatch):
        """The still on screen is the default image, so frame 1 must be put up at once."""
        applied = []
        monkeypatch.setattr(ap.AnimationPlayer, "_apply_frame",
                            lambda self: applied.append(self.current_frame))
        pl = ap.AnimationPlayer(_FakeGui(), _make_apng(tmp_path / "a.png", default_image=True))
        pl.load()
        assert applied == [0]
        applied.clear()
        ap.AnimationPlayer(_FakeGui(), _make_apng(tmp_path / "b.png", default_image=False)).load()
        assert applied == []

    def test_one_frame_after_the_default_image_is_not_an_animation(self, tmp_path):
        path = tmp_path / "a.png"
        Image.new("RGB", (8, 8), "white").save(
            path, save_all=True, append_images=[Image.new("RGB", (8, 8), "red")], default_image=True)
        assert ap.AnimationPlayer(_FakeGui(), str(path)).load() is False
