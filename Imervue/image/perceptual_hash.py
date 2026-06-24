"""Perceptual hashing and near-duplicate grouping (pure, Qt-free).

The difference-hash (dHash) and Hamming-distance helpers plus union-find
clustering that group visually-similar images. Extracted from the duplicate-
detection dialog so the logic is reusable headlessly (CLI / MCP) and unit-
testable without a display server; the dialog now imports from here.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence

from PIL import Image

DEFAULT_HASH_SIZE = 8
DEFAULT_THRESHOLD = 5


def dhash(img: Image.Image, hash_size: int = DEFAULT_HASH_SIZE) -> int:
    """Difference hash: compare adjacent pixel brightness on a tiny grayscale."""
    resized = img.convert("L").resize(
        (hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    # Pillow 14 renamed getdata() → get_flattened_data(); support both.
    get_pixels = getattr(resized, "get_flattened_data", None) or resized.getdata
    pixels = list(get_pixels())
    row_stride = hash_size + 1
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * row_stride + col
            if pixels[idx] < pixels[idx + 1]:
                bits |= 1 << (row * hash_size + col)
    return bits


def ahash(img: Image.Image, hash_size: int = DEFAULT_HASH_SIZE) -> int:
    """Average hash: each pixel brighter than the tile mean sets a bit.

    A different sensitivity to dhash — robust to small local edits but more
    affected by overall brightness shifts — so it complements it for
    near-duplicate detection. Produces the same ``hash_size**2``-bit space, so
    :func:`hamming_distance` compares an ahash with an ahash.
    """
    resized = img.convert("L").resize(
        (hash_size, hash_size), Image.Resampling.LANCZOS)
    get_pixels = getattr(resized, "get_flattened_data", None) or resized.getdata
    pixels = list(get_pixels())
    average = sum(pixels) / len(pixels)
    bits = 0
    for index, value in enumerate(pixels):
        if value >= average:
            bits |= 1 << index
    return bits


def hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two hashes."""
    return bin(a ^ b).count("1")


def hash_paths(
    paths: Iterable[str],
    on_progress: Callable[[int, int], None] | None = None,
    hasher: Callable[[Image.Image], int] | None = None,
) -> list[tuple[str, int]]:
    """Return ``(path, hash)`` for each readable image; unreadable ones skipped.

    ``hasher`` selects the perceptual hash (default :func:`dhash`; pass
    :func:`ahash` for the average-hash variant). When ``on_progress`` is given
    the iterable is materialised so a total is known, and the callback is
    invoked ``(processed, total)`` after each path — including skipped ones — so
    progress always reaches the total.
    """
    hash_fn = hasher or dhash
    items = list(paths) if on_progress is not None else paths
    total = len(items) if on_progress is not None else 0
    hashed: list[tuple[str, int]] = []
    for processed, path in enumerate(items, start=1):
        try:
            with Image.open(path) as img:
                hashed.append((str(path), hash_fn(img)))
        except (OSError, ValueError):
            pass
        if on_progress is not None:
            on_progress(processed, total)
    return hashed


def _find_root(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: list[int], a: int, b: int) -> None:
    ra, rb = _find_root(parent, a), _find_root(parent, b)
    if ra != rb:
        parent[ra] = rb


def group_similar(
    hashed: Sequence[tuple[str, int]], threshold: int = DEFAULT_THRESHOLD,
) -> list[list[str]]:
    """Cluster paths whose hashes are within *threshold* Hamming distance.

    Returns only groups with more than one member, each sorted, outer list
    sorted by first path for deterministic output.
    """
    parent = list(range(len(hashed)))
    for i in range(len(hashed)):
        for j in range(i + 1, len(hashed)):
            if hamming_distance(hashed[i][1], hashed[j][1]) <= threshold:
                _union(parent, i, j)
    clusters: dict[int, list[str]] = defaultdict(list)
    for i, (path, _h) in enumerate(hashed):
        clusters[_find_root(parent, i)].append(path)
    groups = [sorted(members) for members in clusters.values() if len(members) > 1]
    groups.sort(key=lambda g: g[0])
    return groups


def find_similar(
    paths: Iterable[str],
    threshold: int = DEFAULT_THRESHOLD,
    on_progress: Callable[[int, int], None] | None = None,
    hasher: Callable[[Image.Image], int] | None = None,
) -> list[list[str]]:
    """Hash *paths* and return groups of near-duplicate images.

    ``on_progress`` is forwarded to :func:`hash_paths` for per-file progress;
    ``hasher`` selects the perceptual hash (default :func:`dhash`).
    """
    return group_similar(hash_paths(paths, on_progress, hasher), threshold)
