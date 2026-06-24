"""Tests for XMP/EXIF metadata reconciliation."""
from __future__ import annotations

import pytest

from Imervue.image.metadata_sync import (
    merge_metadata,
    percent_to_rating,
    rating_to_percent,
    reconcile_rating,
)


# ---------------------------------------------------------------------------
# rating <-> percent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stars,percent", [
    (0, 0), (1, 1), (2, 25), (3, 50), (4, 75), (5, 99),
])
def test_rating_to_percent(stars, percent):
    assert rating_to_percent(stars) == percent


def test_rating_to_percent_clamps():
    assert rating_to_percent(9) == 99
    assert rating_to_percent(-1) == 0   # rejected has no percent form


@pytest.mark.parametrize("stars", [0, 1, 2, 3, 4, 5])
def test_percent_round_trips_back_to_stars(stars):
    assert percent_to_rating(rating_to_percent(stars)) == stars


def test_percent_to_rating_boundaries():
    assert percent_to_rating(0) == 0
    assert percent_to_rating(12) == 1
    assert percent_to_rating(13) == 2
    assert percent_to_rating(87) == 4
    assert percent_to_rating(88) == 5
    assert percent_to_rating(100) == 5


def test_percent_to_rating_clamps():
    assert percent_to_rating(-50) == 0
    assert percent_to_rating(500) == 5


# ---------------------------------------------------------------------------
# reconcile_rating
# ---------------------------------------------------------------------------


def test_reconcile_prefers_xmp_by_default():
    assert reconcile_rating(4, 2) == 4


def test_reconcile_prefers_exif_when_asked():
    assert reconcile_rating(4, 2, prefer="exif") == 2


def test_reconcile_falls_back_when_primary_missing():
    assert reconcile_rating(None, 3) == 3
    assert reconcile_rating(5, None, prefer="exif") == 5


def test_reconcile_both_missing_is_zero():
    assert reconcile_rating(None, None) == 0


def test_reconcile_unknown_prefer_raises():
    with pytest.raises(ValueError, match="prefer must be"):
        reconcile_rating(1, 2, prefer="iptc")


# ---------------------------------------------------------------------------
# merge_metadata
# ---------------------------------------------------------------------------


def test_merge_fills_unset_fields():
    primary = {"title": "Sunset", "creator": ""}
    secondary = {"creator": "Ansel", "keywords": ["sky"]}
    merged = merge_metadata(primary, secondary)
    assert merged == {"title": "Sunset", "creator": "Ansel", "keywords": ["sky"]}


def test_merge_primary_set_value_wins():
    merged = merge_metadata({"title": "A"}, {"title": "B"})
    assert merged["title"] == "A"


def test_merge_does_not_mutate_inputs():
    primary = {"title": ""}
    secondary = {"title": "B"}
    merge_metadata(primary, secondary)
    assert primary == {"title": ""}
    assert secondary == {"title": "B"}


def test_merge_empty_list_is_unset():
    merged = merge_metadata({"keywords": []}, {"keywords": ["a", "b"]})
    assert merged["keywords"] == ["a", "b"]
