"""Capture-time correction — shift EXIF timestamps across a selection.

The universal "my camera clock was wrong / set to the wrong time zone" fix, as
offered by Lightroom's *Edit Capture Time* and ``exiftool -AllDates+=``. The
user either dials in a delta directly or names the correct time for one
reference frame; the same delta is then applied to every selected photo, and a
collision-free set of EXIF rewrites is planned for the writer to consume.

Pure ``datetime`` arithmetic — no pixel work, no optional deps. Trivially
unit-testable on synthetic ``(path, datetime)`` lists.
"""
from __future__ import annotations

from datetime import datetime, timedelta

EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def delta_to_match(reference_actual: datetime, reference_correct: datetime) -> timedelta:
    """Return the shift that maps *reference_actual* onto *reference_correct*.

    Sample one frame whose true capture time you know; the returned delta,
    applied to the whole selection, corrects every frame by the same amount.
    """
    return reference_correct - reference_actual


def shift_capture_time(
    items: list[tuple[str, datetime]], delta: timedelta,
) -> list[tuple[str, datetime]]:
    """Return *items* with *delta* added to each capture time (order preserved).

    Raises ``OverflowError`` if a shift would fall outside ``datetime``'s range.
    """
    return [(path, when + delta) for path, when in items]


def plan_exif_rewrites(
    items: list[tuple[str, datetime]], delta: timedelta,
) -> list[tuple[str, str]]:
    """Return ``(path, new_exif_string)`` pairs for the shifted capture times.

    The string is formatted as EXIF ``DateTimeOriginal`` (``YYYY:MM:DD HH:MM:SS``)
    so it can be written straight back to the file's metadata.
    """
    return [
        (path, when.strftime(EXIF_DATETIME_FORMAT))
        for path, when in shift_capture_time(items, delta)
    ]
