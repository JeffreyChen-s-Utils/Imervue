"""Tests for the vertical-layout text mode and selection-path text."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.text_on_selection import (
    _decimate,
    render_text_along_selection,
)
from Imervue.paint.text_render import TextRenderOptions, render_text


# ---------------------------------------------------------------------------
# Vertical layout
# ---------------------------------------------------------------------------


def test_vertical_text_produces_taller_buffer_than_horizontal(qapp):
    """Same string + font but vertical mode should yield a buffer
    whose height significantly exceeds its width — the classic
    manga column block."""
    horizontal = render_text(TextRenderOptions(text="ABCD", size=36))
    vertical = render_text(TextRenderOptions(text="ABCD", size=36, vertical=True))
    assert horizontal.shape[2] == 4
    assert vertical.shape[2] == 4
    assert vertical.shape[0] >= vertical.shape[1]
    # Height should be roughly proportional to character count for
    # vertical layout, while horizontal stays compact.
    assert vertical.shape[0] > horizontal.shape[0]


def test_vertical_text_renders_at_least_some_glyphs(qapp):
    arr = render_text(TextRenderOptions(text="X", size=48, vertical=True))
    # At least one opaque pixel — the glyph hit the canvas.
    assert int(arr[..., 3].max()) > 0


def test_text_tool_dialog_round_trips_vertical_flag(qapp):
    from Imervue.paint.text_tool import TextToolDialog
    dialog = TextToolDialog(initial_color=(0, 0, 0))
    try:
        # Default: vertical off.
        assert dialog.options().vertical is False
        dialog._vertical.setChecked(True)            # noqa: SLF001
        assert dialog.options().vertical is True
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Path text from selection
# ---------------------------------------------------------------------------


def test_decimate_drops_collinear_dense_points():
    pts = [(0.0, 0.0), (0.1, 0.0), (0.2, 0.0), (5.0, 0.0)]
    decimated = _decimate(pts, min_spacing=1.0)
    assert decimated[0] == (0.0, 0.0)
    assert decimated[-1] == (5.0, 0.0)
    # The two intermediate near-zero points must drop because they
    # sit within 1 pixel of the seed.
    assert (0.1, 0.0) not in decimated
    assert (0.2, 0.0) not in decimated


def test_decimate_handles_empty_input():
    assert _decimate([], min_spacing=1.0) == []


def test_render_text_along_selection_returns_canvas_sized_buffer(qapp):
    """A simple square selection produces a non-empty buffer of the
    requested canvas shape with at least some opaque text pixels."""
    h, w = 64, 96
    mask = np.zeros((h, w), dtype=bool)
    mask[10:50, 20:80] = True
    arr = render_text_along_selection(
        mask, "AB", (h, w), size=18, color=(0, 0, 0),
    )
    assert arr.shape == (h, w, 4)
    assert int(arr[..., 3].max()) > 0


def test_render_text_along_selection_empty_mask_returns_blank(qapp):
    h, w = 32, 32
    mask = np.zeros((h, w), dtype=bool)
    arr = render_text_along_selection(mask, "Hello", (h, w))
    assert arr.shape == (h, w, 4)
    assert int(arr[..., 3].max()) == 0


def test_render_text_along_selection_rejects_wrong_shape():
    h, w = 32, 32
    mask = np.ones((h, w + 4), dtype=bool)
    with pytest.raises(ValueError, match="selection_mask shape"):
        render_text_along_selection(mask, "X", (h, w))


def test_render_text_along_selection_rejects_non_boolean_mask():
    h, w = 8, 8
    mask = np.ones((h, w), dtype=np.uint8)
    with pytest.raises(ValueError, match="boolean"):
        render_text_along_selection(mask, "X", (h, w))
