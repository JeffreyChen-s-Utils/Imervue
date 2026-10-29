"""
重複圖片分群
Duplicate clustering helpers — union-find over perceptual hashes (no Qt).

Used by the duplicate scan worker to merge images whose hashes lie within the
sensitivity threshold into groups, in first-seen scan order.
"""
from __future__ import annotations


def _flatten_hash_map(
    hash_map: dict[str, list[tuple[str, int]]],
) -> list[tuple[int, str, int]]:
    return [
        (int(h_str), path, size)
        for h_str, items in hash_map.items()
        for path, size in items
    ]


def _find_root(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find_root(parent, a), _find_root(parent, b)
    if ra != rb:
        parent[ra] = rb


def _build_clusters(
    entries: list[tuple[int, str, int]],
    parent: list[int],
) -> list[list[tuple[str, int]]]:
    from collections import defaultdict
    clusters: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for i, (_h, path, size) in enumerate(entries):
        clusters[_find_root(parent, i)].append((path, size))
    return [g for g in clusters.values() if len(g) > 1]
