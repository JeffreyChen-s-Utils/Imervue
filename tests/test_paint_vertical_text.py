"""Tests for vertical text rendering."""
from __future__ import annotations

import numpy as np

from Imervue.paint.text_render import TextRenderOptions, render_text


def test_vertical_text_returns_rgba(qapp):
    out = render_text(TextRenderOptions(text="ABC", vertical=True))
    assert out.dtype == np.uint8
    assert out.ndim == 3
    assert out.shape[2] == 4


def test_vertical_text_taller_than_horizontal(qapp):
    """Three letters stacked vertically should produce a buffer
    taller than the horizontal version of the same string."""
    horizontal = render_text(TextRenderOptions(text="ABC", vertical=False))
    vertical = render_text(TextRenderOptions(text="ABC", vertical=True))
    assert vertical.shape[0] > horizontal.shape[0]


def test_vertical_text_narrower_than_horizontal(qapp):
    """Vertical text fits in roughly one glyph's width — narrower
    than the horizontal three-letter run."""
    horizontal = render_text(TextRenderOptions(text="ABC", vertical=False))
    vertical = render_text(TextRenderOptions(text="ABC", vertical=True))
    assert vertical.shape[1] < horizontal.shape[1]


def test_vertical_text_empty_string_returns_zero_array(qapp):
    out = render_text(TextRenderOptions(text="", vertical=True))
    assert out.shape == (0, 0, 4)


def test_vertical_text_color_appears_in_pixels(qapp):
    out = render_text(TextRenderOptions(
        text="A", vertical=True, color=(255, 0, 0),
    ))
    # At least one pixel should pick up the requested colour.
    red_pixels = np.where((out[..., 0] > 200) & (out[..., 3] > 0))
    assert len(red_pixels[0]) > 0


def test_vertical_text_line_spacing_increases_height(qapp):
    tight = render_text(TextRenderOptions(
        text="ABC", vertical=True, line_spacing=1.0,
    ))
    loose = render_text(TextRenderOptions(
        text="ABC", vertical=True, line_spacing=2.0,
    ))
    assert loose.shape[0] > tight.shape[0]


def test_vertical_text_single_char(qapp):
    """Single character vertical render should still produce a
    sensible buffer (not zero-sized)."""
    out = render_text(TextRenderOptions(text="A", vertical=True))
    assert out.shape[0] > 0
    assert out.shape[1] > 0
    assert (out[..., 3] > 0).any()


def test_vertical_text_size_clamped_above_max(qapp):
    out = render_text(TextRenderOptions(
        text="A", vertical=True, size=10000,
    ))
    # Output is bounded — the size clamp prevents a runaway allocation.
    assert out.shape[0] < 5000
    assert out.shape[1] < 5000


def test_vertical_text_glyphs_centred_horizontally(qapp):
    """A wide glyph defines the column width; a narrow glyph below
    it should leave roughly equal blank space on each side."""
    out = render_text(TextRenderOptions(
        text="WI", vertical=True, size=80,
    ))
    # The column has alpha somewhere on the left half AND somewhere
    # on the right half — i.e. centring isn't pinned hard left.
    h = out.shape[0]
    half = out.shape[1] // 2
    left_half_painted = (out[:, :half, 3] > 0).any()
    right_half_painted = (out[:, half:, 3] > 0).any()
    assert left_half_painted
    assert right_half_painted
    # Both characters' rows have alpha somewhere.
    top_third = out[:h // 3, :, 3]
    bottom_third = out[2 * h // 3:, :, 3]
    assert (top_third > 0).any()
    assert (bottom_third > 0).any()
