"""Tests for palette matching + extraction."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.match_palette import (
    MAX_PALETTE_SIZE,
    match_palette,
    palette_from_image,
)


def _solid(rgb, h=4, w=4):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[..., 0] = rgb[0]
    img[..., 1] = rgb[1]
    img[..., 2] = rgb[2]
    img[..., 3] = 255
    return img


# ---------------------------------------------------------------------------
# match_palette
# ---------------------------------------------------------------------------


def test_match_palette_single_colour_quantises_everything():
    img = _solid((100, 50, 25))
    out = match_palette(img, [(255, 255, 255)])
    assert (out[..., :3] == 255).all()


def test_match_palette_two_colour_picks_nearest():
    img = _solid((10, 10, 10))   # very dark
    out = match_palette(img, [(0, 0, 0), (255, 255, 255)])
    # Should map to black (closer to 10,10,10 than to white).
    assert tuple(out[0, 0, :3]) == (0, 0, 0)


def test_match_palette_three_colours_partition_correctly():
    """A red pixel maps to the palette's red, not to its blue."""
    img = _solid((250, 10, 10))
    out = match_palette(
        img, [(0, 0, 255), (255, 0, 0), (0, 255, 0)],
    )
    assert tuple(out[0, 0, :3]) == (255, 0, 0)


def test_match_palette_empty_returns_copy():
    img = _solid((100, 50, 25))
    out = match_palette(img, [])
    np.testing.assert_array_equal(out, img)


def test_match_palette_corrupt_entries_skipped():
    """Entries that aren't a valid 3-tuple are silently dropped; the
    remaining palette is used. Here only one valid entry remains."""
    img = _solid((100, 100, 100))
    out = match_palette(
        img, [(255, 0, 0), "garbage", [10, 20]],   # type: ignore[list-item]
    )
    # Only red survives the cleanup → all pixels become red.
    assert tuple(out[0, 0, :3]) == (255, 0, 0)


def test_match_palette_all_corrupt_returns_copy():
    img = _solid((100, 100, 100))
    out = match_palette(img, ["bad", [1, 2]])  # type: ignore[list-item]
    np.testing.assert_array_equal(out, img)


def test_match_palette_alpha_preserved():
    img = _solid((128, 128, 128))
    img[..., 3] = 200
    out = match_palette(img, [(255, 255, 255)])
    assert (out[..., 3] == 200).all()


def test_match_palette_clamps_oversized_components():
    img = _solid((100, 100, 100))
    out = match_palette(img, [(300, -50, 200)])
    # Overflowed components clamp to (255, 0, 200).
    assert tuple(out[0, 0, :3]) == (255, 0, 200)


def test_match_palette_rejects_non_rgba_image():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        match_palette(rgb, [(0, 0, 0)])


def test_match_palette_rejects_oversized_palette():
    img = _solid((0, 0, 0))
    huge = [(i % 256, 0, 0) for i in range(MAX_PALETTE_SIZE + 1)]
    with pytest.raises(ValueError, match=str(MAX_PALETTE_SIZE)):
        match_palette(img, huge)


# ---------------------------------------------------------------------------
# palette_from_image
# ---------------------------------------------------------------------------


def test_palette_from_image_returns_most_common_colours():
    """A 4-pixel image with one dominant colour and one rare one
    should return both — dominant first."""
    img = np.zeros((4, 4, 4), dtype=np.uint8)
    img[..., :3] = (10, 20, 30)
    img[..., 3] = 255
    img[0, 0, :3] = (200, 100, 50)
    palette = palette_from_image(img, max_colors=2)
    # Most common is the (10, 20, 30) bg; less common is (200, 100, 50).
    assert (10, 20, 30) in palette
    assert (200, 100, 50) in palette
    assert palette[0] == (10, 20, 30)   # dominant first


def test_palette_from_image_caps_at_max_colors():
    img = np.zeros((10, 10, 4), dtype=np.uint8)
    img[..., 3] = 255
    for x in range(10):
        for y in range(10):
            img[y, x, :3] = (x * 25, y * 25, 0)
    palette = palette_from_image(img, max_colors=4)
    assert len(palette) == 4


def test_palette_from_image_rejects_zero_max_colors():
    img = _solid((0, 0, 0))
    with pytest.raises(ValueError, match="max_colors"):
        palette_from_image(img, max_colors=0)


def test_palette_from_image_rejects_non_rgba():
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        palette_from_image(rgb)


def test_palette_then_match_round_trip_quantises_to_one_color():
    """Extract a 1-entry palette from a uniform image; matching back
    produces the same image."""
    img = _solid((100, 50, 25))
    palette = palette_from_image(img, max_colors=1)
    out = match_palette(img, palette)
    np.testing.assert_array_equal(out[..., :3], img[..., :3])
