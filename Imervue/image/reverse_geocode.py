"""Offline reverse geocoding — map (lat, lon) to the nearest major city.

Photos carry GPS coordinates but no human-readable place name. Rather than
send a user's location to an external service (a privacy-sensitive, outward
call), this resolves coordinates against a small bundled table of major world
cities and returns the nearest one as ``"City, Country"``.

The result is therefore *approximate* — it names the nearest sizeable city,
not the exact street — which is what photo organisation usually wants. A
precise online provider can be layered on later as an explicit opt-in.

Everything here is pure and offline, so it is fully unit-testable and never
touches the network.
"""
from __future__ import annotations

import math
from functools import lru_cache

_EARTH_RADIUS_KM = 6371.0
# Round coordinates before the cached lookup so nearby points share a result
# (≈1 km at 2 decimals) and the cache actually hits during a browse session.
_CACHE_PRECISION = 2

# (city, country, latitude, longitude) — a compact, globally spread set of
# major cities. Coordinates are to ~2 decimals, which is plenty for a
# nearest-city match.
_CITIES: tuple[tuple[str, str, float, float], ...] = (
    ("New York", "United States", 40.71, -74.01),
    ("Los Angeles", "United States", 34.05, -118.24),
    ("Chicago", "United States", 41.88, -87.63),
    ("San Francisco", "United States", 37.77, -122.42),
    ("Seattle", "United States", 47.61, -122.33),
    ("Las Vegas", "United States", 36.17, -115.14),
    ("Miami", "United States", 25.76, -80.19),
    ("Washington", "United States", 38.91, -77.04),
    ("Boston", "United States", 42.36, -71.06),
    ("Toronto", "Canada", 43.65, -79.38),
    ("Vancouver", "Canada", 49.28, -123.12),
    ("Montreal", "Canada", 45.50, -73.57),
    ("Mexico City", "Mexico", 19.43, -99.13),
    ("Sao Paulo", "Brazil", -23.55, -46.63),
    ("Rio de Janeiro", "Brazil", -22.91, -43.17),
    ("Buenos Aires", "Argentina", -34.60, -58.38),
    ("Lima", "Peru", -12.05, -77.04),
    ("Bogota", "Colombia", 4.71, -74.07),
    ("Santiago", "Chile", -33.45, -70.67),
    ("London", "United Kingdom", 51.51, -0.13),
    ("Paris", "France", 48.85, 2.35),
    ("Berlin", "Germany", 52.52, 13.40),
    ("Munich", "Germany", 48.14, 11.58),
    ("Madrid", "Spain", 40.42, -3.70),
    ("Barcelona", "Spain", 41.39, 2.17),
    ("Rome", "Italy", 41.90, 12.50),
    ("Milan", "Italy", 45.46, 9.19),
    ("Amsterdam", "Netherlands", 52.37, 4.90),
    ("Brussels", "Belgium", 50.85, 4.35),
    ("Vienna", "Austria", 48.21, 16.37),
    ("Zurich", "Switzerland", 47.37, 8.54),
    ("Prague", "Czech Republic", 50.08, 14.44),
    ("Warsaw", "Poland", 52.23, 21.01),
    ("Stockholm", "Sweden", 59.33, 18.07),
    ("Copenhagen", "Denmark", 55.68, 12.57),
    ("Oslo", "Norway", 59.91, 10.75),
    ("Helsinki", "Finland", 60.17, 24.94),
    ("Dublin", "Ireland", 53.35, -6.26),
    ("Lisbon", "Portugal", 38.72, -9.14),
    ("Athens", "Greece", 37.98, 23.73),
    ("Moscow", "Russia", 55.76, 37.62),
    ("Istanbul", "Turkey", 41.01, 28.98),
    ("Cairo", "Egypt", 30.04, 31.24),
    ("Lagos", "Nigeria", 6.52, 3.38),
    ("Nairobi", "Kenya", -1.29, 36.82),
    ("Johannesburg", "South Africa", -26.20, 28.05),
    ("Cape Town", "South Africa", -33.92, 18.42),
    ("Casablanca", "Morocco", 33.57, -7.59),
    ("Dubai", "United Arab Emirates", 25.20, 55.27),
    ("Tel Aviv", "Israel", 32.08, 34.78),
    ("Riyadh", "Saudi Arabia", 24.71, 46.68),
    ("Tokyo", "Japan", 35.68, 139.69),
    ("Osaka", "Japan", 34.69, 135.50),
    ("Seoul", "South Korea", 37.57, 126.98),
    ("Beijing", "China", 39.90, 116.41),
    ("Shanghai", "China", 31.23, 121.47),
    ("Hong Kong", "China", 22.32, 114.17),
    ("Taipei", "Taiwan", 25.03, 121.57),
    ("Singapore", "Singapore", 1.35, 103.82),
    ("Bangkok", "Thailand", 13.76, 100.50),
    ("Kuala Lumpur", "Malaysia", 3.14, 101.69),
    ("Jakarta", "Indonesia", -6.21, 106.85),
    ("Manila", "Philippines", 14.60, 120.98),
    ("Mumbai", "India", 19.08, 72.88),
    ("Delhi", "India", 28.61, 77.21),
    ("Bangalore", "India", 12.97, 77.59),
    ("Dhaka", "Bangladesh", 23.81, 90.41),
    ("Karachi", "Pakistan", 24.86, 67.01),
    ("Ho Chi Minh City", "Vietnam", 10.82, 106.63),
    ("Sydney", "Australia", -33.87, 151.21),
    ("Melbourne", "Australia", -37.81, 144.96),
    ("Brisbane", "Australia", -27.47, 153.03),
    ("Perth", "Australia", -31.95, 115.86),
    ("Auckland", "New Zealand", -36.85, 174.76),
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lon points."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2)
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def nearest_city(lat: float, lon: float) -> tuple[str, str, float] | None:
    """Return ``(city, country, distance_km)`` of the nearest table entry."""
    best: tuple[str, str, float] | None = None
    for name, country, clat, clon in _CITIES:
        distance = haversine_km(lat, lon, clat, clon)
        if best is None or distance < best[2]:
            best = (name, country, distance)
    return best


@lru_cache(maxsize=4096)
def _cached_place(lat_rounded: float, lon_rounded: float) -> str | None:
    nearest = nearest_city(lat_rounded, lon_rounded)
    if nearest is None:
        return None
    name, country, _distance = nearest
    return f"{name}, {country}"


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Return ``"City, Country"`` for the nearest major city, or ``None``.

    Coordinates are rounded before the cached lookup so a browse session over
    photos from the same place reuses one computation.
    """
    return _cached_place(round(lat, _CACHE_PRECISION), round(lon, _CACHE_PRECISION))
