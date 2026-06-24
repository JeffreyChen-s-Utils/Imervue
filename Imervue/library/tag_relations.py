"""Related-tag suggestions from tag co-occurrence.

When tagging an image, the tags that most often appear *with* a given tag are
useful suggestions. The pure core :func:`related_tags` ranks tags by shared
image count over a ``tag -> set(paths)`` membership map, so it needs no DB to
test; :func:`suggest_related` builds that map from the live image index.
"""
from __future__ import annotations

from collections.abc import Mapping


def related_tags(
    target: str,
    membership: Mapping[str, set[str]],
    *,
    limit: int | None = None,
) -> list[tuple[str, int]]:
    """Rank tags by how many images they share with *target*.

    *membership* maps each tag to its set of image paths. Returns
    ``[(tag, shared_count)]`` for tags other than *target* that share at least
    one image, sorted by descending count then tag name. ``limit`` caps the
    result length when given.
    """
    target_paths = membership.get(target)
    if not target_paths:
        return []
    scored = [
        (tag, shared)
        for tag, paths in membership.items()
        if tag != target and (shared := len(target_paths & paths)) > 0
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored if limit is None else scored[:limit]


def suggest_related(target: str, *, limit: int | None = 10) -> list[tuple[str, int]]:
    """Suggest tags related to *target* from the live index by co-occurrence.

    Uses literal tag membership (no descendant expansion) so suggestions
    reflect tags actually applied together rather than parent/child overlap.
    """
    from Imervue.library import image_index
    membership = {
        tag: set(image_index.images_with_tag(tag, include_descendants=False))
        for tag in image_index.all_tag_paths()
    }
    return related_tags(target, membership, limit=limit)
