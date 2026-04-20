"""
Calendar index — bucket images by capture date for Calendar View.

Groups a list of image paths into a mapping of ``date`` → ``list[path]``
so the calendar widget can show counts per day and drill down into the
photos taken on a chosen date. Capture date is read from:

1. EXIF ``DateTimeOriginal`` (tag 0x9003) — canonical capture time.
2. EXIF ``DateTimeDigitized`` (tag 0x9004) — same on most cameras.
3. Filesystem mtime — fallback so screenshots and exports still appear.

Paths where no date can be derived are returned via a sentinel
``UNKNOWN_DATE``.
"""
from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger("Imervue.calendar_index")

UNKNOWN_DATE = _dt.date.min  # sentinel — falsey compare with == UNKNOWN_DATE


_EXIF_DT_ORIGINAL = 0x9003
_EXIF_DT_DIGITIZED = 0x9004
_EXIF_IFD = 0x8769  # sub-IFD where DateTimeOriginal actually lives on some images
_EXIF_DT_TOP = 0x0132  # DateTime at the top-level IFD


def _parse_exif_datetime(value: str) -> _dt.date | None:
    """EXIF datetimes look like ``YYYY:MM:DD HH:MM:SS`` — date portion only."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        head = value.split(" ", 1)[0]
        y, m, d = head.split(":")
        return _dt.date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None


def capture_date(path: str | Path) -> _dt.date:
    """Return the capture date (EXIF original → EXIF digitised → mtime)."""
    p = Path(path)
    try:
        with Image.open(p) as im:
            exif = im.getexif()
    except (OSError, ValueError):
        exif = None

    if exif:
        sub_ifd = {}
        try:
            sub_ifd = exif.get_ifd(_EXIF_IFD)
        except (AttributeError, KeyError, ValueError, OSError):
            sub_ifd = {}
        for source in (sub_ifd, exif):
            for tag in (_EXIF_DT_ORIGINAL, _EXIF_DT_DIGITIZED, _EXIF_DT_TOP):
                dt = _parse_exif_datetime(source.get(tag, ""))
                if dt is not None:
                    return dt
    try:
        ts = p.stat().st_mtime
    except OSError:
        return UNKNOWN_DATE
    return _dt.date.fromtimestamp(ts)


def group_by_date(paths: list[str | Path]) -> dict[_dt.date, list[str]]:
    """Return ``{date: [path, ...]}`` — entries are sorted by path."""
    out: dict[_dt.date, list[str]] = {}
    for p in paths:
        out.setdefault(capture_date(p), []).append(str(p))
    for k in out:
        out[k].sort()
    return out


def group_by_month(
    paths: list[str | Path],
) -> dict[tuple[int, int], list[str]]:
    """Return ``{(year, month): [path, ...]}`` for higher-level navigation."""
    by_day = group_by_date(paths)
    out: dict[tuple[int, int], list[str]] = {}
    for date, items in by_day.items():
        if date == UNKNOWN_DATE:
            continue
        out.setdefault((date.year, date.month), []).extend(items)
    for k in out:
        out[k].sort()
    return out


def date_histogram(paths: list[str | Path]) -> dict[_dt.date, int]:
    """Return ``{date: count}`` — useful for badging calendar cells."""
    return {d: len(items) for d, items in group_by_date(paths).items()}
