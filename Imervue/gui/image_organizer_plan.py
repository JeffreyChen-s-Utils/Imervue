"""
圖片整理規劃
Image Organizer planning — scan a folder and group its images into subfolder
buckets by date, resolution, file type, file size or fixed count. Pure, no
Qt and no side effects; :mod:`Imervue.gui.image_organizer_dialog` re-exports it.
"""
from __future__ import annotations

import os
from pathlib import Path

from Imervue.image.dimensions import image_dimensions
from Imervue.image.formats import JPEG_EXTENSIONS, STILL_IMAGE_EXTENSIONS
from Imervue.library.calendar_index import UNKNOWN_DATETIME, capture_datetime
from Imervue.system.image_listing import list_images

RULE_DATE = "date"
RULE_RESOLUTION = "resolution"
RULE_TYPE = "type"
RULE_SIZE = "size"
RULE_COUNT = "count"


# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------

def _scan_folder(folder: str) -> list[str]:
    """Return image paths in *folder* (non-recursive), in natural name order."""
    return list_images(folder, STILL_IMAGE_EXTENSIONS)


# ---------------------------------------------------------------------------
# Planning — pure function, no side effects
# ---------------------------------------------------------------------------

def _get_image_date(path: str, year_only: bool) -> str:
    """Return a date-based subfolder name for *path*."""
    taken = capture_datetime(path)
    if taken == UNKNOWN_DATETIME:
        return "unknown"
    return taken.strftime("%Y" if year_only else "%Y-%m")


def _get_resolution_bucket(path: str) -> str:
    """Classify image by its longer edge."""
    dims = image_dimensions(path)
    if dims is None:
        return "unknown"
    longest = max(dims)
    if longest >= 3840:
        return "4K+"
    if longest >= 1920:
        return "1080p+"
    if longest >= 1280:
        return "720p+"
    return "small"


def _get_type_bucket(path: str) -> str:
    """Return a normalised extension group name."""
    ext = Path(path).suffix.lower()
    if ext in JPEG_EXTENSIONS:
        return "JPG"
    return ext.lstrip(".").upper() or "OTHER"


def _get_size_bucket(path: str, large_mb: float, small_mb: float) -> str:
    """Classify by file size."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "unknown"
    if size >= large_mb * 1024 * 1024:
        return "large"
    if size >= small_mb * 1024 * 1024:
        return "medium"
    return "small"


def plan_organization(
    paths: list[str],
    rule: str,
    *,
    year_only: bool = False,
    large_mb: float = 5.0,
    small_mb: float = 1.0,
    count_per_folder: int = 100,
) -> dict[str, list[str]]:
    """Return ``{subfolder_name: [paths]}`` without touching the filesystem."""
    plan: dict[str, list[str]] = {}
    for i, p in enumerate(paths):
        if rule == RULE_DATE:
            bucket = _get_image_date(p, year_only)
        elif rule == RULE_RESOLUTION:
            bucket = _get_resolution_bucket(p)
        elif rule == RULE_TYPE:
            bucket = _get_type_bucket(p)
        elif rule == RULE_SIZE:
            bucket = _get_size_bucket(p, large_mb, small_mb)
        elif rule == RULE_COUNT:
            bucket = f"{(i // count_per_folder) + 1:03d}"
        else:
            bucket = "other"
        plan.setdefault(bucket, []).append(p)
    return plan
