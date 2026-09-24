"""Import XMP sidecar keywords into the library tag index.

Keywords written by the keyword editor or the batch geo-keyword action live in
each image's XMP sidecar. Mirroring them into the SQLite tag index makes them
searchable and usable as Smart Album ``tags_all`` / ``tags_any`` rules.

Lightroom and darktable also write the keyword hierarchy
(``lr:hierarchicalSubject``, ``Places|Taiwan|Taipei``); it becomes the library's
tag path ``Places/Taiwan/Taipei``, and the flat keywords that are only levels
of such a path (Lightroom lists every level in ``dc:subject``) are not added a
second time as loose tags.

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


def tag_paths(keywords: list[str], hierarchical: list[str]) -> list[str]:
    """The library tag paths for an image's flat *keywords* and its *hierarchical* ones.

    ``"Places|Taiwan|Taipei"`` becomes ``"Places/Taiwan/Taipei"``; a flat
    keyword naming any level of a hierarchy is covered by it and dropped.
    """
    paths: list[str] = []
    levels: set[str] = set()
    for entry in hierarchical:
        parts = [part.strip() for part in entry.split("|") if part.strip()]
        if parts:
            paths.append("/".join(parts))
            levels.update(parts)
    return paths + [keyword for keyword in keywords if keyword.strip() not in levels]


def import_keywords_to_index(paths: Iterable[str]) -> int:
    """Add every XMP keyword (hierarchies as tag paths) as library tags; returns photos updated."""
    from Imervue.image import xmp_sidecar
    from Imervue.library import image_index

    updated = 0
    for path in paths:
        data = xmp_sidecar.load(path)
        keywords = tag_paths(data.keywords, data.hierarchical_keywords)
        if not keywords:
            continue
        additions = new_keywords(image_index.tags_of_image(path), keywords)
        for tag in additions:
            image_index.add_image_tag(path, tag)
        if additions:
            updated += 1
    return updated
