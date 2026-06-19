"""Find images with incomplete metadata (no location / keywords / title / creator).

A triage/QA helper: surface photos still missing a property so they can be
tagged or geocoded. The "which required fields are missing" decision is pure
and unit-tested; presence detection reads the XMP sidecar and GPS.
"""
from __future__ import annotations

from collections.abc import Iterable

FIELDS = ("location", "keywords", "title", "creator")


def missing_fields(presence: dict, required: list[str]) -> list[str]:
    """Return the *required* fields that are absent (falsy) in *presence*."""
    return [field for field in required if not presence.get(field)]


def image_metadata_presence(path: str) -> dict:
    """Return which tracked metadata fields are present for *path*."""
    from Imervue.image import xmp_sidecar
    from Imervue.image.gps import extract_gps
    xmp = xmp_sidecar.load(path)
    return {
        "location": extract_gps(path) is not None,
        "keywords": bool(xmp.keywords),
        "title": bool(xmp.title),
        "creator": bool(xmp.creator),
    }


def paths_missing(paths: Iterable[str], required: list[str]) -> list[str]:
    """Return paths that are missing any of the *required* metadata fields."""
    wanted = [field for field in required if field in FIELDS]
    if not wanted:
        return []
    return [
        path for path in paths
        if missing_fields(image_metadata_presence(path), wanted)
    ]
