"""Tests for trim / bleed / safe-area guide geometry."""
from __future__ import annotations

import pytest

from Imervue.paint.bleed_guides import (
    DEFAULT_BLEED_MM,
    DEFAULT_SAFE_MM,
    MAX_MARGIN_MM,
    PRESETS,
    BleedGuides,
    available_presets,
    preset,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_default_construction_uses_documented_margins():
    g = BleedGuides(trim_width_mm=100.0, trim_height_mm=100.0)
    assert g.bleed_mm == DEFAULT_BLEED_MM
    assert g.safe_mm == DEFAULT_SAFE_MM


def test_rejects_zero_trim_width():
    with pytest.raises(ValueError, match="trim_width_mm"):
        BleedGuides(trim_width_mm=0, trim_height_mm=100)


def test_rejects_negative_trim_height():
    with pytest.raises(ValueError, match="trim_height_mm"):
        BleedGuides(trim_width_mm=100, trim_height_mm=-1)


def test_rejects_oversized_bleed():
    with pytest.raises(ValueError, match="bleed_mm"):
        BleedGuides(
            trim_width_mm=100, trim_height_mm=100,
            bleed_mm=MAX_MARGIN_MM + 1,
        )


def test_rejects_oversized_safe():
    """Safe margin can't exceed half the smaller trim dimension."""
    with pytest.raises(ValueError, match="safe_mm"):
        BleedGuides(
            trim_width_mm=20.0, trim_height_mm=20.0, safe_mm=15.0,
        )


def test_rejects_zero_dpi():
    with pytest.raises(ValueError, match="dpi"):
        BleedGuides(trim_width_mm=100, trim_height_mm=100, dpi=0)


# ---------------------------------------------------------------------------
# page_pixel_size
# ---------------------------------------------------------------------------


def test_page_pixel_size_includes_bleed():
    """Page = trim + bleed on every side, in pixels."""
    g = BleedGuides(
        trim_width_mm=100.0, trim_height_mm=200.0,
        bleed_mm=10.0, safe_mm=0.0, dpi=72,
    )
    # 100 + 2*10 = 120 mm wide → 340.16 → 340 px at 72 DPI.
    expected_w = int(round(120.0 * 72 / 25.4))
    expected_h = int(round(220.0 * 72 / 25.4))
    assert g.page_pixel_size == (expected_w, expected_h)


# ---------------------------------------------------------------------------
# Rect helpers
# ---------------------------------------------------------------------------


def test_trim_rect_inset_by_bleed():
    g = BleedGuides(
        trim_width_mm=100.0, trim_height_mm=100.0,
        bleed_mm=10.0, safe_mm=0.0, dpi=72,
    )
    bleed_px = int(round(10.0 * 72 / 25.4))
    trim_w = int(round(100.0 * 72 / 25.4))
    assert g.trim_rect_px() == (bleed_px, bleed_px, trim_w, trim_w)


def test_safe_rect_inset_by_bleed_plus_safe():
    g = BleedGuides(
        trim_width_mm=100.0, trim_height_mm=100.0,
        bleed_mm=10.0, safe_mm=5.0, dpi=72,
    )
    bleed_px = int(round(10.0 * 72 / 25.4))
    safe_px = int(round(5.0 * 72 / 25.4))
    safe_w = int(round((100.0 - 2 * 5.0) * 72 / 25.4))
    expected = (bleed_px + safe_px, bleed_px + safe_px, safe_w, safe_w)
    assert g.safe_rect_px() == expected


def test_bleed_rect_origin_at_zero():
    g = BleedGuides(trim_width_mm=100, trim_height_mm=100, dpi=72)
    rect = g.bleed_rect_px()
    assert rect[0] == 0
    assert rect[1] == 0


def test_three_rects_are_concentric():
    """Centres of trim / bleed / safe must coincide on integer pixels
    (the conversions use rounding so a small drift is acceptable)."""
    g = BleedGuides(
        trim_width_mm=100, trim_height_mm=100,
        bleed_mm=5, safe_mm=2, dpi=300,
    )
    bleed = g.bleed_rect_px()
    trim = g.trim_rect_px()
    safe = g.safe_rect_px()
    # Each ``*_rect_px`` returns ``(x, y, w, h)`` so the rectangle
    # centre lives at ``x + w / 2``.
    bleed_cx = bleed[0] + bleed[2] / 2
    trim_cx = trim[0] + trim[2] / 2
    safe_cx = safe[0] + safe[2] / 2
    assert abs(bleed_cx - trim_cx) < 1.0
    assert abs(bleed_cx - safe_cx) < 1.0


def test_safe_rect_inside_trim_rect():
    g = BleedGuides(
        trim_width_mm=100, trim_height_mm=100,
        bleed_mm=5, safe_mm=10, dpi=300,
    )
    trim = g.trim_rect_px()
    safe = g.safe_rect_px()
    assert safe[0] >= trim[0]
    assert safe[1] >= trim[1]
    assert safe[0] + safe[2] <= trim[0] + trim[2]
    assert safe[1] + safe[3] <= trim[1] + trim[3]


def test_trim_rect_inside_bleed_rect():
    g = BleedGuides(
        trim_width_mm=100, trim_height_mm=100,
        bleed_mm=5, safe_mm=2, dpi=300,
    )
    bleed = g.bleed_rect_px()
    trim = g.trim_rect_px()
    assert trim[0] >= bleed[0]
    assert trim[0] + trim[2] <= bleed[0] + bleed[2]


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


def test_presets_includes_documented_set():
    assert {"manga_b5", "manga_b4", "a4", "a5"} <= set(available_presets())


def test_preset_returns_known_guides():
    g = preset("manga_b5")
    assert g.trim_width_mm == 182.0


def test_preset_unknown_raises():
    with pytest.raises(KeyError, match="unknown"):
        preset("does-not-exist")


def test_preset_table_uses_3mm_bleed_default():
    """JIS B5 manga uses the 3 mm bleed convention."""
    assert PRESETS["manga_b5"].bleed_mm == 3.0
