"""Place rules for Smart Albums: match a geocoded place and group by city.

Pure matching plus the GPS-backed ``place`` filter; persisting the generated
albums stays in :mod:`Imervue.library.smart_album`.
"""
from __future__ import annotations


def place_matches(found: str | None, wanted: str) -> bool:
    """Whether the geocoded *found* (``"City, Country"``) is the *wanted* place.

    *wanted* names the city, the country or both, in any case: ``Paris``,
    ``france`` and ``Paris, France`` all match ``"Paris, France"``. A typed
    ``place:Paris`` compared the whole string and never matched.
    """
    if not found:
        return False
    parts = [part.strip().lower() for part in found.split(",")]
    asked = [part.strip().lower() for part in wanted.split(",") if part.strip()]
    return asked == parts or (len(asked) == 1 and asked[0] in parts)


def _apply_place_filter(paths: list[str], place: str) -> list[str]:
    """Keep paths whose GPS reverse-geocodes to *place* (see :func:`place_matches`).

    Runs last (after the cheap filters narrow the set) because it extracts EXIF
    GPS per file. Untagged images can't match a place, so they drop out.
    """
    from Imervue.image.gps import extract_gps
    from Imervue.image.reverse_geocode import reverse_geocode
    out: list[str] = []
    for path in paths:
        coords = extract_gps(path)
        if coords is not None and place_matches(reverse_geocode(coords[0], coords[1]), place):
            out.append(path)
    return out


def auto_location_albums(
    path_coords: list[tuple[str, float, float]],
) -> list[tuple[str, dict]]:
    """Group ``(path, lat, lon)`` into one ``(album_name, rules)`` per city.

    Pure: the album name is the nearest-city place and its rule is a matching
    ``place`` filter. Returned sorted by name for stable output.
    """
    from Imervue.image.reverse_geocode import reverse_geocode
    buckets: dict[str, list[str]] = {}
    for path, lat, lon in path_coords:
        place = reverse_geocode(lat, lon)
        if place:
            buckets.setdefault(place, []).append(path)
    return [(place, {"place": place}) for place in sorted(buckets)]
