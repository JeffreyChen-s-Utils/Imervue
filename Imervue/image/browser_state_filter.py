"""Browse-filter specification and path filtering.

``ImageFilterSpec`` holds the structured fields plus the raw query;
``filter_paths`` applies it through an optional metadata index, and
``refilter_keeping_current`` keeps an explicitly opened image visible.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from Imervue.image.browser_state_index import ImageMetadataIndex
from Imervue.image.browser_state_query import (
    _match_raw_query,
    _rating_matches,
    _tag_matches,
)


@dataclass(frozen=True)
class ImageFilterSpec:
    filename: str = ""
    tag: str = ""
    rating: str = ""
    date_from: date | None = None
    date_to: date | None = None
    raw_query: str = ""

    def is_empty(self) -> bool:
        return not any((
            self.filename.strip(),
            self.tag.strip(),
            self.rating.strip(),
            self.date_from,
            self.date_to,
            self.raw_query.strip(),
        ))


def match_filter(path: str, spec: ImageFilterSpec,
                 index: ImageMetadataIndex | None = None) -> bool:
    meta = (index.get_stat(path) if index is not None
            else ImageMetadataIndex._read(path, with_dimensions=False)[0])
    filename = spec.filename.strip().lower()
    if filename and filename not in meta.name:
        return False
    if spec.tag.strip() and not _tag_matches(path, spec.tag):
        return False
    if spec.rating.strip() and not _rating_matches(path, spec.rating.strip()):
        return False
    if not _date_in_range(meta.mtime_date, spec.date_from, spec.date_to):
        return False
    return _match_raw_query(path, spec.raw_query, meta)


def _date_in_range(actual: date | None, date_from: date | None, date_to: date | None) -> bool:
    if not (date_from or date_to):
        return True
    if actual is None:
        return False
    if date_from and actual < date_from:
        return False
    return not (date_to and actual > date_to)


def filter_paths(paths: Iterable[str], spec: ImageFilterSpec,
                 index: ImageMetadataIndex | None = None) -> list[str]:
    if spec.is_empty():
        return list(paths)
    return [path for path in paths if match_filter(path, spec, index)]


def refilter_keeping_current(base: list[str], filtered: list[str],
                             current: str | None) -> list[str]:
    """Return *filtered*, but force *current* back in at its folder position.

    Opening a specific file (a Modify save, an image-tab switch) rebuilds the
    list from the full folder and drops the active browse filter. Re-applying
    the filter restores it, but the explicitly-opened image must stay visible
    even when it doesn't match — you asked to see that file — rather than the
    filter navigating away from it. Insert it back at its position in *base* so
    the strip/list keeps folder order. A no-op when *current* is falsy, already
    kept, or not part of *base*.
    """
    if not current or current in filtered or current not in base:
        return filtered
    pos_of = {path: i for i, path in enumerate(base)}
    current_pos = pos_of[current]
    insert_at = sum(1 for path in filtered if pos_of.get(path, -1) < current_pos)
    result = list(filtered)
    result.insert(insert_at, current)
    return result

