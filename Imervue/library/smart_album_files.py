"""Per-file rule filters for Smart Albums: filename patterns, stat and EXIF.

Each takes the surviving path list and returns the narrowed one;
:func:`Imervue.library.smart_album.apply_to_paths` decides the order.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path


def _apply_name_pattern_filters(paths: list[str], rules: dict) -> list[str]:
    """Filter by a filename regex (``name_regex``) and/or glob (``name_glob``)."""
    name_regex = rules.get("name_regex")
    if name_regex:
        try:
            compiled = re.compile(name_regex)
        except re.error:
            return []  # an unparsable pattern matches nothing
        paths = [p for p in paths if compiled.search(Path(p).name)]
    name_glob = rules.get("name_glob")
    if name_glob:
        pattern = name_glob.lower()
        paths = [p for p in paths if fnmatch.fnmatch(Path(p).name.lower(), pattern)]
    return paths


def _apply_size_filters(paths: list[str], rules: dict) -> list[str]:
    """Filter by file size in bytes (``min_size`` / ``max_size``) via stat."""
    min_size = rules.get("min_size")
    max_size = rules.get("max_size")
    if not min_size and not max_size:
        return paths
    out: list[str] = []
    for p in paths:
        try:
            size = Path(p).stat().st_size
        except OSError:
            continue
        if min_size and size < int(min_size):
            continue
        if max_size and size > int(max_size):
            continue
        out.append(p)
    return out


def _apply_date_filter(
    paths: list[str], date_from: float | None, date_to: float | None,
) -> list[str]:
    out: list[str] = []
    for p in paths:
        try:
            mtime = Path(p).stat().st_mtime
        except OSError:
            continue
        if date_from and mtime < float(date_from):
            continue
        if date_to and mtime > float(date_to):
            continue
        out.append(p)
    return out


def _contains_ci(needle: str, haystack: str) -> bool:
    return needle.lower() in haystack.lower()


def _apply_exif_filters(paths: list[str], rules: dict) -> list[str]:
    """Keep paths whose EXIF make/model (``camera``) or lens (``lens``) match.

    Runs late (after the cheap filters) because it reads EXIF per file.
    Untagged images carry no camera/lens, so a camera/lens rule drops them.
    """
    camera = rules.get("camera")
    lens = rules.get("lens")
    if not camera and not lens:
        return paths
    from Imervue.image.exif_merge import get_exif_data
    out: list[str] = []
    for path in paths:
        exif = get_exif_data(Path(path))
        body = f"{exif.get('Make', '')} {exif.get('Model', '')}"
        if camera and not _contains_ci(camera, body):
            continue
        if lens and not _contains_ci(lens, str(exif.get("LensModel", ""))):
            continue
        out.append(path)
    return out
