"""Batch location keywords — write a photo's place into its XMP keywords.

For each geotagged photo, reverse-geocode the nearest city and merge
``[city, country]`` into the image's XMP sidecar ``dc:subject`` keywords. This
is portable (other XMP-aware tools read it) and reversible (delete the sidecar).

Builds on :mod:`Imervue.image.reverse_geocode` and :mod:`Imervue.image.xmp_sidecar`.
The merge logic is pure and unit-tested; the orchestrator does the file I/O.
"""
from __future__ import annotations

from collections.abc import Iterable


def merge_keywords(existing: list[str], new: list[str]) -> list[str]:
    """Append *new* keywords to *existing*, preserving order and de-duplicating."""
    merged = list(existing)
    for keyword in new:
        if keyword and keyword not in merged:
            merged.append(keyword)
    return merged


def tag_paths_by_location(paths: Iterable[str]) -> int:
    """Write nearest-city keywords into each geotagged path's XMP sidecar.

    Returns the number of photos whose keywords were updated (unchanged sidecars
    are left untouched).
    """
    from Imervue.image import xmp_sidecar
    from Imervue.image.gps import collect_gps
    from Imervue.image.reverse_geocode import place_keywords

    tagged = 0
    for path, lat, lon in collect_gps(list(paths)):
        keywords = place_keywords(lat, lon)
        if not keywords:
            continue
        data = xmp_sidecar.load(path)
        merged = merge_keywords(data.keywords, keywords)
        if merged != data.keywords:
            data.keywords = merged
            xmp_sidecar.save(path, data)
            tagged += 1
    return tagged
