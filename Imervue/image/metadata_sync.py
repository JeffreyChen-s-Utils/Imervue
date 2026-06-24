"""Reconcile rating / metadata between XMP and EXIF representations.

XMP stores a 0-5 star rating (with -1 = rejected); the EXIF / Windows world
stores ``RatingPercent`` (0-100). The Metadata Working Group defines a fixed
mapping between them — this module implements just that well-defined part,
plus picking a rating when the two sources disagree and a gap-filling field
merge. It works on already-loaded values (ints / dicts), so it stays pure: no
file reading, no vendor maker-note guessing, no Qt.
"""
from __future__ import annotations

from typing import Any

MAX_STARS = 5
MIN_PERCENT = 0
MAX_PERCENT = 100
# MWG / Windows star -> percent mapping, indexed by star count (0-5).
_STARS_TO_PERCENT = (0, 1, 25, 50, 75, 99)
# Reverse boundaries: percent below the i-th value maps to i stars.
_PERCENT_BOUNDARIES = (13, 38, 63, 88)


def rating_to_percent(stars: int) -> int:
    """Map a 0-5 star rating to its MWG ``RatingPercent`` (0-100).

    Stars are clamped to ``[0, 5]``; the XMP "rejected" rating (-1) has no
    percent representation and maps to 0.
    """
    clamped = max(0, min(MAX_STARS, int(stars)))
    return _STARS_TO_PERCENT[clamped]


def percent_to_rating(percent: int) -> int:
    """Map an EXIF/Windows ``RatingPercent`` (0-100) to a 0-5 star rating."""
    value = max(MIN_PERCENT, min(MAX_PERCENT, int(percent)))
    if value <= 0:
        return 0
    return sum(1 for boundary in _PERCENT_BOUNDARIES if value >= boundary) + 1


def reconcile_rating(
    xmp_rating: int | None, exif_rating: int | None, *, prefer: str = "xmp",
) -> int:
    """Pick a single rating from possibly-conflicting XMP and EXIF values.

    The *prefer* source wins when both are present; otherwise the other fills
    in, and 0 is returned when neither is set. Raises :class:`ValueError` for an
    unknown *prefer*.
    """
    if prefer not in ("xmp", "exif"):
        raise ValueError(f"prefer must be 'xmp' or 'exif', got {prefer!r}")
    primary, secondary = (
        (xmp_rating, exif_rating) if prefer == "xmp" else (exif_rating, xmp_rating)
    )
    if primary is not None:
        return int(primary)
    if secondary is not None:
        return int(secondary)
    return 0


def _is_set(value: Any) -> bool:
    return value is not None and value not in ("", [])


def merge_metadata(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Return *primary* with any unset field filled from *secondary*.

    A field is "set" when it is not ``None`` / ``""`` / ``[]``. Keys present
    only in *secondary* are added. Neither input is mutated.
    """
    merged = dict(primary)
    for key, value in secondary.items():
        if not _is_set(merged.get(key)) and _is_set(value):
            merged[key] = value
    return merged
