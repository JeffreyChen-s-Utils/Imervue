"""Tests for offline reverse geocoding (nearest-city lookup + cache)."""
from __future__ import annotations

import pytest

from Imervue.image.reverse_geocode import (
    _cached_place,
    haversine_km,
    nearest_city,
    reverse_geocode,
)


# ---------------------------------------------------------------------------
# haversine_km
# ---------------------------------------------------------------------------


def test_haversine_same_point_is_zero():
    assert haversine_km(48.85, 2.35, 48.85, 2.35) == pytest.approx(0.0, abs=1e-6)


def test_haversine_london_to_paris():
    # London → Paris is roughly 340 km.
    distance = haversine_km(51.51, -0.13, 48.85, 2.35)
    assert 330 < distance < 360


# ---------------------------------------------------------------------------
# nearest_city
# ---------------------------------------------------------------------------


def test_nearest_city_picks_closest():
    name, country, distance = nearest_city(48.86, 2.34)  # next to Paris
    assert name == "Paris"
    assert country == "France"
    assert distance < 5


def test_nearest_city_tokyo():
    name, country, _distance = nearest_city(35.7, 139.7)
    assert name == "Tokyo"
    assert country == "Japan"


# ---------------------------------------------------------------------------
# reverse_geocode
# ---------------------------------------------------------------------------


def test_reverse_geocode_format():
    assert reverse_geocode(40.71, -74.01) == "New York, United States"


def test_reverse_geocode_remote_point_returns_nearest():
    # Mid-Pacific — still returns the best available guess, never None.
    result = reverse_geocode(0.0, -160.0)
    assert result is not None
    assert ", " in result


def test_reverse_geocode_cache_buckets_nearby_points():
    _cached_place.cache_clear()
    reverse_geocode(48.851, 2.349)
    before = _cached_place.cache_info()  # pylint: disable=no-value-for-parameter
    reverse_geocode(48.853, 2.351)  # rounds to the same (48.85, 2.35)
    after = _cached_place.cache_info()  # pylint: disable=no-value-for-parameter
    assert after.hits == before.hits + 1
