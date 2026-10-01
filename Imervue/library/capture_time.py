"""Capture-time correction — shift EXIF timestamps across a selection.

The universal "my camera clock was wrong / set to the wrong time zone" fix, as
offered by Lightroom's *Edit Capture Time* and ``exiftool -AllDates+=``. The
user either dials in a delta directly or names the correct time for one
reference frame; the same delta is then applied to every selected photo, and a
collision-free set of EXIF rewrites is planned for the writer to consume.

The arithmetic is pure ``datetime`` work, trivially unit-testable on synthetic
``(path, datetime)`` lists; :func:`exif_capture_time` and
:func:`write_capture_time` read and rewrite the three EXIF dates of one JPEG or
WebP in place. **Extra Tools > Library & Metadata > Edit Capture Time** drives them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"
_DATETIME = 0x0132              # IFD0: when the file was last changed
_DATETIME_ORIGINAL = 0x9003     # Exif IFD: when the shutter fired
_DATETIME_DIGITIZED = 0x9004    # Exif IFD: when it was digitised
_EXIF_IFD = 0x8769

logger = logging.getLogger("Imervue.library.capture_time")


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


def exif_capture_time(path: str | Path) -> datetime | None:
    """The EXIF capture time of *path* (DateTimeOriginal, else DateTimeDigitized), or None.

    Unlike :func:`~Imervue.library.date_import.extract_capture_date` there is
    no file-time fallback: a photo without an EXIF date has nothing to correct
    or correlate.
    """
    from Imervue.image.exif_merge import get_exif_data
    from Imervue.library.date_import import parse_exif_datetime
    exif = get_exif_data(Path(path)) or {}
    return parse_exif_datetime(exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized"))


def write_capture_time(path: str | Path, exif_text: str) -> bool:
    """Set DateTimeOriginal, DateTimeDigitized and DateTime of *path* to *exif_text*.

    Only the EXIF block is rewritten (the photo's Modify recipe follows it).
    False, with the file untouched, for a format whose EXIF can't be rewritten
    in place (anything but JPEG and WebP) or a write that failed.
    """
    from Imervue.image.in_place_save import can_rewrite_exif, rewrite_exif
    if not Path(path).is_file() or not can_rewrite_exif(path):
        return False
    stamp = str(exif_text)       # ASCII digits, so a str tag is written as-is

    def set_dates(exif) -> None:
        exif[_DATETIME] = stamp
        sub = exif.get_ifd(_EXIF_IFD)
        sub[_DATETIME_ORIGINAL] = stamp
        sub[_DATETIME_DIGITIZED] = stamp
        exif[_EXIF_IFD] = exif.get(_EXIF_IFD, 0)   # the save writes the IFD and its real offset

    try:
        rewrite_exif(path, set_dates)
    except (ValueError, OSError) as err:
        logger.warning("Failed to write the capture time of %s: %s", path, err)
        return False
    return True
