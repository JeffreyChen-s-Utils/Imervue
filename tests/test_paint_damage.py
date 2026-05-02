"""Tests for the damage-rectangle helper."""
from __future__ import annotations

from Imervue.paint.damage import EMPTY, DamageRect, from_dab_result


# ---------------------------------------------------------------------------
# Construction / properties
# ---------------------------------------------------------------------------


def test_default_rect_is_empty():
    assert DamageRect().is_empty
    assert EMPTY.is_empty


def test_rect_with_zero_extent_is_empty():
    assert DamageRect(x=10, y=10, w=0, h=5).is_empty
    assert DamageRect(x=10, y=10, w=5, h=0).is_empty


def test_rect_with_negative_extent_is_empty():
    assert DamageRect(x=10, y=10, w=-5, h=5).is_empty


def test_x2_and_y2_derive_from_corner_plus_extent():
    rect = DamageRect(x=3, y=4, w=5, h=6)
    assert rect.x2 == 8
    assert rect.y2 == 10


# ---------------------------------------------------------------------------
# union
# ---------------------------------------------------------------------------


def test_union_two_overlapping_rects():
    a = DamageRect(x=0, y=0, w=10, h=10)
    b = DamageRect(x=5, y=5, w=10, h=10)
    union = a.union(b)
    assert (union.x, union.y, union.w, union.h) == (0, 0, 15, 15)


def test_union_disjoint_rects():
    a = DamageRect(x=0, y=0, w=5, h=5)
    b = DamageRect(x=10, y=10, w=5, h=5)
    union = a.union(b)
    assert (union.x, union.y, union.w, union.h) == (0, 0, 15, 15)


def test_union_with_empty_returns_other():
    a = DamageRect(x=2, y=3, w=4, h=5)
    assert a.union(EMPTY) == a
    assert EMPTY.union(a) == a


def test_union_two_empty_rects_is_empty():
    assert EMPTY.union(EMPTY).is_empty


# ---------------------------------------------------------------------------
# inflate
# ---------------------------------------------------------------------------


def test_inflate_grows_each_side_by_margin():
    rect = DamageRect(x=10, y=20, w=4, h=6)
    grown = rect.inflate(2)
    assert (grown.x, grown.y, grown.w, grown.h) == (8, 18, 8, 10)


def test_inflate_passes_empty_through_unchanged():
    """An empty rect must not become non-empty after inflation —
    otherwise a no-damage stroke would still trigger a partial upload."""
    inflated = EMPTY.inflate(5)
    assert inflated.is_empty


def test_inflate_negative_shrinks():
    rect = DamageRect(x=0, y=0, w=10, h=10)
    shrunk = rect.inflate(-1)
    assert (shrunk.x, shrunk.y, shrunk.w, shrunk.h) == (1, 1, 8, 8)


# ---------------------------------------------------------------------------
# clipped_to
# ---------------------------------------------------------------------------


def test_clipped_to_clips_left_edge():
    rect = DamageRect(x=-5, y=0, w=10, h=5)
    clipped = rect.clipped_to((20, 20))
    assert (clipped.x, clipped.y, clipped.w, clipped.h) == (0, 0, 5, 5)


def test_clipped_to_clips_right_and_bottom():
    rect = DamageRect(x=15, y=15, w=10, h=10)
    clipped = rect.clipped_to((20, 20))
    assert (clipped.x, clipped.y, clipped.w, clipped.h) == (15, 15, 5, 5)


def test_clipped_to_fully_off_canvas_is_empty():
    rect = DamageRect(x=100, y=100, w=10, h=10)
    assert rect.clipped_to((20, 20)).is_empty


def test_clipped_to_empty_input_returns_empty():
    assert EMPTY.clipped_to((20, 20)).is_empty


# ---------------------------------------------------------------------------
# covers_full
# ---------------------------------------------------------------------------


def test_covers_full_true_when_rect_at_least_as_large_as_canvas():
    rect = DamageRect(x=0, y=0, w=20, h=20)
    assert rect.covers_full((20, 20))


def test_covers_full_true_for_oversized_rect():
    """A rect that extends past the canvas counts as full coverage —
    the partial-upload path saves nothing here."""
    rect = DamageRect(x=-5, y=-5, w=30, h=30)
    assert rect.covers_full((20, 20))


def test_covers_full_false_for_partial_rect():
    rect = DamageRect(x=5, y=5, w=10, h=10)
    assert not rect.covers_full((20, 20))


def test_covers_full_false_for_empty_rect():
    assert not EMPTY.covers_full((20, 20))


# ---------------------------------------------------------------------------
# from_dab_result interop
# ---------------------------------------------------------------------------


def test_from_dab_result_copies_coordinates():
    from Imervue.paint.brush_engine import DabResult
    dab = DabResult(x=10, y=20, w=5, h=6)
    rect = from_dab_result(dab)
    assert (rect.x, rect.y, rect.w, rect.h) == (10, 20, 5, 6)


def test_from_dab_result_empty_dab_yields_empty_rect():
    from Imervue.paint.brush_engine import DabResult
    rect = from_dab_result(DabResult(0, 0, 0, 0))
    assert rect.is_empty
