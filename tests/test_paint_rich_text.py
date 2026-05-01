"""Tests for the rich-text per-character style model + rasteriser."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.rich_text import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_TEXT_COLOR,
    TEXT_SIZE_MAX,
    TEXT_SIZE_MIN,
    StyledRun,
    StyledText,
    TextStyle,
    render_styled_text,
)


# ---------------------------------------------------------------------------
# TextStyle
# ---------------------------------------------------------------------------


def test_default_style_uses_documented_defaults():
    style = TextStyle()
    assert style.font_family == DEFAULT_FONT_FAMILY
    assert style.font_size == DEFAULT_FONT_SIZE
    assert style.color == DEFAULT_TEXT_COLOR


def test_style_rejects_too_small_font():
    with pytest.raises(ValueError):
        TextStyle(font_size=TEXT_SIZE_MIN - 1)


def test_style_rejects_too_large_font():
    with pytest.raises(ValueError):
        TextStyle(font_size=TEXT_SIZE_MAX + 1)


def test_style_rejects_invalid_color_component():
    with pytest.raises(ValueError):
        TextStyle(color=(300, 0, 0, 255))


def test_style_round_trips_via_dict():
    style = TextStyle(
        font_family="Verdana", font_size=42,
        bold=True, italic=False, color=(10, 20, 30, 200),
    )
    rebuilt = TextStyle.from_dict(style.to_dict())
    assert rebuilt == style


def test_style_from_dict_garbage_falls_back():
    out = TextStyle.from_dict("not a dict")
    assert out == TextStyle()


def test_style_from_dict_invalid_size_falls_back():
    out = TextStyle.from_dict({"font_size": "huge"})
    assert out == TextStyle()


# ---------------------------------------------------------------------------
# StyledRun + StyledText basics
# ---------------------------------------------------------------------------


def test_styled_run_rejects_non_string_text():
    with pytest.raises(ValueError):
        StyledRun(text=None)   # type: ignore[arg-type]


def test_styled_text_append_grows_runs():
    text = StyledText()
    assert text.total_length() == 0
    text.append("Hello")
    text.append(" world")
    assert text.total_length() == 11
    assert text.plain_text() == "Hello world"


def test_styled_text_from_plain_creates_one_run():
    text = StyledText.from_plain("Bubble", style=TextStyle(font_size=18))
    assert len(text.runs) == 1
    assert text.runs[0].text == "Bubble"


def test_styled_text_round_trip_via_dict():
    text = StyledText()
    text.append("Hi", style=TextStyle(color=(255, 0, 0, 255)))
    text.append("!", style=TextStyle(font_size=48, bold=True))
    rebuilt = StyledText.from_dict(text.to_dict())
    assert rebuilt.plain_text() == "Hi!"
    assert rebuilt.runs[1].style.bold is True


def test_styled_text_from_dict_garbage_returns_empty():
    out = StyledText.from_dict("not a dict")
    assert out.runs == []


# ---------------------------------------------------------------------------
# merge_adjacent
# ---------------------------------------------------------------------------


def test_merge_adjacent_collapses_same_style():
    text = StyledText()
    text.append("Hel")
    text.append("lo")
    text.merge_adjacent()
    assert len(text.runs) == 1
    assert text.runs[0].text == "Hello"


def test_merge_adjacent_preserves_different_styles():
    text = StyledText()
    text.append("Hi", style=TextStyle(color=(255, 0, 0, 255)))
    text.append("!", style=TextStyle(color=(0, 255, 0, 255)))
    text.merge_adjacent()
    assert len(text.runs) == 2


def test_merge_adjacent_drops_empty_runs():
    text = StyledText()
    text.append("Hi")
    text.append("")
    text.append("!")
    text.merge_adjacent()
    assert text.plain_text() == "Hi!"
    assert all(r.text for r in text.runs)


# ---------------------------------------------------------------------------
# apply_style
# ---------------------------------------------------------------------------


def test_apply_style_in_middle_of_run_splits_into_three():
    text = StyledText.from_plain("Hello world")
    red = TextStyle(color=(255, 0, 0, 255))
    text.apply_style(start=2, end=5, style=red)
    # Should produce: "He" / "llo" (red) / " world"
    assert len(text.runs) == 3
    assert text.runs[1].text == "llo"
    assert text.runs[1].style.color == (255, 0, 0, 255)


def test_apply_style_at_run_boundary_does_not_create_empties():
    text = StyledText.from_plain("Hello")
    bold = TextStyle(bold=True)
    text.apply_style(start=0, end=5, style=bold)
    text.merge_adjacent()
    assert len(text.runs) == 1
    assert text.runs[0].style.bold is True


def test_apply_style_clamps_out_of_range_indices():
    text = StyledText.from_plain("Hi")
    bold = TextStyle(bold=True)
    text.apply_style(start=-10, end=999, style=bold)
    text.merge_adjacent()
    assert text.runs[0].style.bold is True


def test_apply_style_zero_range_is_noop():
    text = StyledText.from_plain("Hi")
    text.apply_style(start=1, end=1, style=TextStyle(bold=True))
    assert text.plain_text() == "Hi"


def test_apply_style_spans_multiple_runs():
    text = StyledText()
    text.append("Hello, ", style=TextStyle())
    text.append("world", style=TextStyle(color=(255, 0, 0, 255)))
    text.append("!", style=TextStyle())
    big = TextStyle(font_size=36)
    text.apply_style(start=3, end=10, style=big)
    # The big style cuts across all three runs.
    affected = [r for r in text.runs if r.style.font_size == 36]
    assert len(affected) >= 1
    big_total = sum(len(r.text) for r in affected)
    assert big_total == 7   # "lo, wor"


# ---------------------------------------------------------------------------
# render_styled_text
# ---------------------------------------------------------------------------


def test_render_empty_text_returns_one_pixel():
    out = render_styled_text(StyledText())
    assert out.shape == (1, 1, 4)


def test_render_returns_rgba_uint8():
    text = StyledText.from_plain("Hi", style=TextStyle(font_size=20))
    out = render_styled_text(text)
    assert out.dtype == np.uint8
    assert out.shape[2] == 4


def test_render_paints_some_visible_pixels():
    text = StyledText.from_plain("Hi", style=TextStyle(font_size=24))
    out = render_styled_text(text)
    # At least one pixel must be visibly opaque.
    assert int(out[..., 3].max()) > 0


def test_render_respects_canvas_size_argument():
    text = StyledText.from_plain("X", style=TextStyle(font_size=24))
    out = render_styled_text(text, canvas_size=(80, 40))
    assert out.shape == (40, 80, 4)


def test_render_rejects_zero_canvas_size():
    text = StyledText.from_plain("X", style=TextStyle(font_size=24))
    with pytest.raises(ValueError):
        render_styled_text(text, canvas_size=(0, 40))


def test_render_returns_contiguous_buffer():
    text = StyledText.from_plain("Hi", style=TextStyle(font_size=20))
    out = render_styled_text(text)
    assert out.flags["C_CONTIGUOUS"]


def test_render_handles_newline_in_text():
    text = StyledText.from_plain("First\nSecond", style=TextStyle(font_size=24))
    out = render_styled_text(text)
    # Multi-line means height must exceed a single line worth of pixels.
    assert out.shape[0] > 24


def test_render_different_colours_per_run_yield_different_pixels():
    """Two runs with different colours render to materially different
    pixel values somewhere in the output."""
    a_text = StyledText()
    a_text.append("XX", style=TextStyle(color=(255, 0, 0, 255), font_size=32))
    b_text = StyledText()
    b_text.append("XX", style=TextStyle(color=(0, 0, 255, 255), font_size=32))
    a = render_styled_text(a_text)
    b = render_styled_text(b_text)
    assert not np.array_equal(a, b)
