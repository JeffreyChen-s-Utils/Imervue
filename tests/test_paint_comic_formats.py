"""Tests for the comic-format presets."""
from __future__ import annotations

import pytest

from Imervue.paint.bleed_guides import BleedGuides
from Imervue.paint.comic_formats import (
    COMIC_FORMATS,
    ComicFormat,
    find_format,
    format_names,
)


# ---------------------------------------------------------------------------
# ComicFormat validation
# ---------------------------------------------------------------------------


def test_format_rejects_blank_name():
    with pytest.raises(ValueError, match="name"):
        ComicFormat(name="", label="L", trim_width_mm=100, trim_height_mm=100)


def test_format_rejects_blank_label():
    with pytest.raises(ValueError, match="label"):
        ComicFormat(name="n", label="", trim_width_mm=100, trim_height_mm=100)


def test_format_rejects_zero_trim():
    with pytest.raises(ValueError, match="trim"):
        ComicFormat(
            name="n", label="L", trim_width_mm=0, trim_height_mm=100,
        )


def test_format_rejects_negative_bleed():
    with pytest.raises(ValueError, match="bleed/safe"):
        ComicFormat(
            name="n", label="L", trim_width_mm=100, trim_height_mm=100,
            bleed_mm=-1.0,
        )


def test_format_rejects_zero_dpi():
    with pytest.raises(ValueError, match="dpi"):
        ComicFormat(
            name="n", label="L", trim_width_mm=100, trim_height_mm=100, dpi=0,
        )


def test_format_rejects_zero_default_rows():
    with pytest.raises(ValueError, match="default rows/cols"):
        ComicFormat(
            name="n", label="L", trim_width_mm=100, trim_height_mm=100,
            default_rows=0, default_cols=4,
        )


# ---------------------------------------------------------------------------
# Built-in catalogue
# ---------------------------------------------------------------------------


def test_built_in_catalogue_is_non_empty():
    assert len(COMIC_FORMATS) >= 5


def test_every_format_has_unique_name():
    names = [fmt.name for fmt in COMIC_FORMATS]
    assert len(set(names)) == len(names)


def test_format_names_returns_canonical_order():
    assert format_names() == [fmt.name for fmt in COMIC_FORMATS]


def test_find_format_known_name_returns_format():
    assert find_format("manga_b5") is not None


def test_find_format_unknown_name_returns_none():
    assert find_format("not-a-format") is None


@pytest.mark.parametrize("name", [fmt.name for fmt in COMIC_FORMATS])
def test_each_built_in_yields_valid_bleed_guides(name):
    fmt = find_format(name)
    assert fmt is not None
    guides = fmt.bleed_guides()
    assert isinstance(guides, BleedGuides)
    # Page size in pixels is positive on both axes.
    w, h = guides.page_pixel_size
    assert w > 0
    assert h > 0


def test_page_pixel_size_matches_bleed_guide():
    fmt = find_format("manga_b5")
    assert fmt is not None
    guides = fmt.bleed_guides()
    assert fmt.page_pixel_size() == guides.page_pixel_size


# ---------------------------------------------------------------------------
# Specific built-in spot checks
# ---------------------------------------------------------------------------


def test_manga_b5_dimensions():
    """B5 manga: 182×257 mm at 350 dpi → ~2509×3543 pixels including
    3mm bleed on all sides."""
    fmt = find_format("manga_b5")
    assert fmt is not None
    w, h = fmt.page_pixel_size()
    # 182+6 = 188 mm * 350 / 25.4 ≈ 2591
    # 257+6 = 263 mm * 350 / 25.4 ≈ 3624
    assert 2400 <= w <= 2700
    assert 3500 <= h <= 3700


def test_yonkoma_vertical_has_4_rows_default():
    fmt = find_format("yonkoma_vertical")
    assert fmt is not None
    assert fmt.default_rows == 4
    assert fmt.default_cols == 1


def test_yonkoma_horizontal_has_4_cols_default():
    fmt = find_format("yonkoma_horizontal")
    assert fmt is not None
    assert fmt.default_rows == 1
    assert fmt.default_cols == 4


def test_webtoon_format_is_tall_and_low_dpi():
    fmt = find_format("webtoon_vertical")
    assert fmt is not None
    assert fmt.dpi == 72
    # Far taller than it is wide.
    assert fmt.trim_height_mm > fmt.trim_width_mm * 5
