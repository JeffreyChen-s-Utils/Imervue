"""Import photos into dated folders by capture date.

Routes files into a ``YYYY/MM`` tree (configurable strftime pattern) using the
EXIF *DateTimeOriginal*, falling back to the file's modification time. The
date parsing and the path-planning (including in-batch name-collision
resolution) are pure and unit-tested; the orchestrator copies/moves the files.
"""
from __future__ import annotations

import shutil
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

_EXIF_DATETIME = "%Y:%m:%d %H:%M:%S"
_DEFAULT_PATTERN = "%Y/%m"


def dated_folder(when: datetime, pattern: str = _DEFAULT_PATTERN) -> str:
    """Return the relative folder for *when* under the given strftime pattern."""
    return when.strftime(pattern)


def parse_exif_datetime(raw: object) -> datetime | None:
    """Parse an EXIF ``YYYY:MM:DD HH:MM:SS`` string, or None if unparseable."""
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), _EXIF_DATETIME)
    except (ValueError, TypeError):
        return None


def plan_import(
    items: list[tuple[str, datetime]], dest_root: str,
    pattern: str = _DEFAULT_PATTERN,
) -> list[tuple[str, str]]:
    """Map ``(src, capture_date)`` to ``(src, dest)`` under ``dest_root/YYYY/MM``.

    In-batch destination collisions get a ``_N`` suffix so two same-named files
    from the same month do not overwrite each other.
    """
    root = Path(dest_root)
    used: set[str] = set()
    plan: list[tuple[str, str]] = []
    for src, when in items:
        folder = root / dated_folder(when, pattern)
        name = Path(src).name
        dest = folder / name
        counter = 1
        while str(dest).lower() in used:
            dest = folder / f"{Path(name).stem}_{counter}{Path(name).suffix}"
            counter += 1
        used.add(str(dest).lower())
        plan.append((src, str(dest)))
    return plan


def extract_capture_date(path: str) -> datetime | None:
    """EXIF capture date for *path*, falling back to file mtime."""
    from Imervue.image.info import get_exif_data
    exif = get_exif_data(Path(path)) or {}
    parsed = parse_exif_datetime(
        exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized"))
    if parsed is not None:
        return parsed
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime)
    except OSError:
        return None


def import_by_date(
    paths: Iterable[str], dest_root: str,
    pattern: str = _DEFAULT_PATTERN, *, move: bool = False,
) -> int:
    """Copy (or move) each path into its dated folder. Returns files handled."""
    items = []
    for path in paths:
        when = extract_capture_date(path)
        if when is not None:
            items.append((path, when))
    handled = 0
    for src, dest in plan_import(items, dest_root, pattern):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        if move:
            shutil.move(src, dest)
        else:
            shutil.copy2(src, dest)
        handled += 1
    return handled
