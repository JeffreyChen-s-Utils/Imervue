"""Tests for animated-image editing (reverse / boomerang / speed / optimize)."""
from __future__ import annotations

from PIL import Image

from Imervue.image.animation_edit import (
    OPERATIONS,
    boomerang,
    drop_duplicate_frames,
    edit_animation,
    load_frames,
    reverse,
    set_speed,
)


def _frame(color):
    return Image.new("RGBA", (8, 8), color)


def _write_gif(path, colors, duration=100):
    frames = [_frame(c) for c in colors]
    frames[0].save(str(path), save_all=True, append_images=frames[1:],
                   duration=duration, loop=0)


def test_reverse_flips_order():
    frames = ["a", "b", "c"]
    out_f, out_d = reverse(frames, [10, 20, 30])
    assert out_f == ["c", "b", "a"]
    assert out_d == [30, 20, 10]


def test_boomerang_appends_reversed_middle():
    out_f, out_d = boomerang(["a", "b", "c"], [10, 20, 30])
    assert out_f == ["a", "b", "c", "b"]
    assert out_d == [10, 20, 30, 20]


def test_boomerang_single_frame_unchanged():
    assert boomerang(["a"], [10]) == (["a"], [10])


def test_set_speed_scales_durations():
    assert set_speed([100, 100], 2.0) == [50, 50]
    assert set_speed([100], 0.5) == [200]


def test_drop_duplicate_merges_durations():
    out_f, out_d = drop_duplicate_frames(["a", "a", "b"], [100, 100, 100])
    assert out_f == ["a", "b"]
    assert out_d == [200, 100]


def test_edit_animation_round_trip(tmp_path):
    src = tmp_path / "anim.gif"
    _write_gif(src, [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)])
    out = tmp_path / "rev.gif"
    count = edit_animation(str(src), "reverse", str(out))
    assert count == 3
    frames, _durations = load_frames(str(out))
    assert len(frames) == 3


def test_edit_boomerang_grows_frames(tmp_path):
    src = tmp_path / "anim.gif"
    _write_gif(src, [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)])
    out = tmp_path / "boom.gif"
    assert edit_animation(str(src), "boomerang", str(out)) == 4


def test_dialog_smoke(qapp, tmp_path):
    from Imervue.gui.animation_edit_dialog import AnimationEditDialog

    src = tmp_path / "anim.gif"
    _write_gif(src, [(255, 0, 0, 255), (0, 0, 255, 255)])
    dialog = AnimationEditDialog(object(), str(src))
    try:
        assert dialog._operation.count() == len(OPERATIONS)
    finally:
        dialog.deleteLater()
