"""Import XMP sidecar keywords into the library tag index.

Keywords written by the keyword editor or the batch geo-keyword action live in
each image's XMP sidecar. Mirroring them into the SQLite tag index makes them
searchable and usable as Smart Album ``tags_all`` / ``tags_any`` rules.

The diff logic is pure and unit-tested; the orchestrator reads sidecars and
writes tags (``add_image_tag`` is idempotent, so re-running is safe).
"""
from __future__ import annotations

from collections.abc import Iterable


def new_keywords(existing_tags: list[str], keywords: list[str]) -> list[str]:
    """Return keywords not already tagged, order-preserving and de-duplicated."""
    have = set(existing_tags)
    out: list[str] = []
    for keyword in keywords:
        if keyword and keyword not in have and keyword not in out:
            out.append(keyword)
    return out


def import_keywords_to_index(paths: Iterable[str]) -> int:
    """Add each path's XMP keywords as library tags. Returns photos updated."""
    from Imervue.image import xmp_sidecar
    from Imervue.library import image_index

    updated = 0
    for path in paths:
        keywords = xmp_sidecar.load(path).keywords
        if not keywords:
            continue
        additions = new_keywords(image_index.tags_of_image(path), keywords)
        for tag in additions:
            image_index.add_image_tag(path, tag)
        if additions:
            updated += 1
    return updated
