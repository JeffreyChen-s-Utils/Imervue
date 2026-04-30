"""Tests for the animation timeline + onion-skin compositor."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.animation import (
    Animation,
    AnimationFrame,
    composite_with_onion_skin,
)
from Imervue.paint.document import PaintDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_with_color(rgb: tuple[int, int, int], h=4, w=4) -> PaintDocument:
    doc = PaintDocument()
    base = np.zeros((h, w, 4), dtype=np.uint8)
    base[..., :3] = rgb
    base[..., 3] = 255
    doc.load_image(base)
    return doc


def _three_frame_animation() -> Animation:
    a = AnimationFrame(_doc_with_color((255, 0, 0)), name="A")
    b = AnimationFrame(_doc_with_color((0, 255, 0)), name="B")
    c = AnimationFrame(_doc_with_color((0, 0, 255)), name="C")
    return Animation(frames=[a, b, c], active_index=1)


# ---------------------------------------------------------------------------
# AnimationFrame
# ---------------------------------------------------------------------------


def test_animation_frame_construction():
    f = AnimationFrame(_doc_with_color((10, 20, 30)), name="F", duration_ms=200)
    assert f.name == "F"
    assert f.duration_ms == 200


def test_animation_frame_clamps_duration_below_min():
    f = AnimationFrame(_doc_with_color((0, 0, 0)), duration_ms=0)
    assert f.duration_ms == 1


def test_animation_frame_clamps_duration_above_max():
    f = AnimationFrame(_doc_with_color((0, 0, 0)), duration_ms=10**9)
    assert f.duration_ms <= 60_000


def test_animation_frame_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        AnimationFrame(_doc_with_color((0, 0, 0)), name="   ")


# ---------------------------------------------------------------------------
# Animation container
# ---------------------------------------------------------------------------


def test_animation_starts_empty_by_default():
    a = Animation()
    assert a.frame_count == 0
    assert a.active_frame() is None


def test_animation_clamps_fps_above_max():
    a = Animation(fps=10**6)
    assert a.fps <= 120


def test_animation_clamps_active_index_above_count():
    f = AnimationFrame(_doc_with_color((0, 0, 0)))
    a = Animation(frames=[f], active_index=99)
    assert a.active_index == 0


def test_animation_add_frame_inserts_after_active():
    a = _three_frame_animation()
    new_frame = AnimationFrame(_doc_with_color((128, 128, 128)), name="new")
    new_index = a.add_frame(new_frame)
    assert new_index == 2   # inserted after the previous active=1
    assert a.frames[2] is new_frame
    assert a.active_index == 2


def test_animation_add_frame_to_empty_appends():
    a = Animation()
    new_frame = AnimationFrame(_doc_with_color((0, 0, 0)))
    a.add_frame(new_frame)
    assert a.frame_count == 1
    assert a.active_index == 0


def test_animation_remove_active_frame_drops_one():
    a = _three_frame_animation()
    assert a.remove_active_frame() is True
    assert a.frame_count == 2
    assert a.active_index == 0


def test_animation_remove_last_frame_returns_false():
    f = AnimationFrame(_doc_with_color((0, 0, 0)))
    a = Animation(frames=[f])
    assert a.remove_active_frame() is False


def test_animation_set_active_index():
    a = _three_frame_animation()
    a.set_active_index(0)
    assert a.active_index == 0


def test_animation_set_active_index_out_of_range_raises():
    a = _three_frame_animation()
    with pytest.raises(IndexError):
        a.set_active_index(99)


# ---------------------------------------------------------------------------
# Onion-skin compositor
# ---------------------------------------------------------------------------


def test_onion_returns_none_for_empty_animation():
    a = Animation()
    assert composite_with_onion_skin(a) is None


def test_onion_with_zero_neighbours_yields_active_only():
    a = _three_frame_animation()
    out = composite_with_onion_skin(a, before_count=0, after_count=0)
    assert out is not None
    # Active frame is index 1 → green.
    assert tuple(out[2, 2, :3]) == (0, 255, 0)


def test_onion_includes_before_neighbour_at_reduced_opacity():
    a = _three_frame_animation()
    out_with = composite_with_onion_skin(a, before_count=1, after_count=0)
    out_without = composite_with_onion_skin(a, before_count=0, after_count=0)
    assert out_with is not None
    assert out_without is not None
    # The two composites should differ (the ghost frame contributes).
    assert not np.array_equal(out_with, out_without)


def test_onion_negative_count_raises():
    a = _three_frame_animation()
    with pytest.raises(ValueError, match=">= 0"):
        composite_with_onion_skin(a, before_count=-1, after_count=0)


def test_onion_opacity_step_above_one_raises():
    a = _three_frame_animation()
    with pytest.raises(ValueError, match="opacity_step"):
        composite_with_onion_skin(a, opacity_step=2.0)


def test_onion_skip_when_before_off_start():
    """Asking for 5 ghosts before frame 0 silently picks up only the
    available neighbours rather than wrapping around."""
    a = _three_frame_animation()
    a.set_active_index(0)
    out = composite_with_onion_skin(a, before_count=5, after_count=0)
    assert out is not None
    # Only the active red frame contributes.
    assert tuple(out[2, 2, :3]) == (255, 0, 0)


def test_onion_skip_when_after_off_end():
    a = _three_frame_animation()
    a.set_active_index(2)
    out = composite_with_onion_skin(a, before_count=0, after_count=5)
    assert out is not None
    assert tuple(out[2, 2, :3]) == (0, 0, 255)


# ---------------------------------------------------------------------------
# render_onion_skin_overlay — ghosts-only buffer for the canvas widget
# ---------------------------------------------------------------------------


def test_overlay_returns_none_for_empty_animation():
    from Imervue.paint.animation import render_onion_skin_overlay
    out = render_onion_skin_overlay(Animation())
    assert out is None


def test_overlay_returns_none_when_no_neighbours_visible():
    """Active frame is the only frame — both before / after are empty
    so the overlay short-circuits to ``None`` instead of returning a
    fully-transparent buffer the canvas would still try to upload."""
    from Imervue.paint.animation import render_onion_skin_overlay
    doc = PaintDocument()
    doc.load_image(np.full((4, 4, 4), 100, dtype=np.uint8))
    anim = Animation(frames=[AnimationFrame(document=doc, name="solo")])
    out = render_onion_skin_overlay(anim, before_count=1, after_count=1)
    assert out is None


def test_overlay_excludes_active_frame_pixels():
    """The active frame must not appear in the overlay — only the
    neighbours' ghosts."""
    from Imervue.paint.animation import render_onion_skin_overlay
    a = _three_frame_animation()
    a.set_active_index(1)
    overlay = render_onion_skin_overlay(a, before_count=1, after_count=1)
    assert overlay is not None
    # Active frame is green (0, 255, 0); ghosts are red + blue. The
    # green channel should not be dominant at any overlay pixel.
    painted = overlay[..., 3] > 0
    assert painted.any()
    assert overlay[painted, 1].max() <= 0


def test_overlay_negative_count_raises():
    from Imervue.paint.animation import render_onion_skin_overlay
    with pytest.raises(ValueError, match=">= 0"):
        render_onion_skin_overlay(_three_frame_animation(), before_count=-1)


def test_overlay_opacity_step_out_of_range_raises():
    from Imervue.paint.animation import render_onion_skin_overlay
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        render_onion_skin_overlay(
            _three_frame_animation(), opacity_step=1.5,
        )


def test_overlay_ghosts_are_translucent_not_opaque():
    """The painted ghost pixels must be partially transparent — that's
    the visual cue artists rely on to distinguish ghosts from the
    active frame."""
    from Imervue.paint.animation import render_onion_skin_overlay
    a = _three_frame_animation()
    a.set_active_index(2)
    overlay = render_onion_skin_overlay(a, before_count=2, after_count=0)
    assert overlay is not None
    painted = overlay[overlay[..., 3] > 0, 3]
    assert painted.size > 0
    assert int(painted.min()) < 255
