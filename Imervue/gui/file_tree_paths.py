"""Classify selected paths and allocate duplicate filenames."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def _next_duplicate_name(source: Path) -> Path:
    """Pick a sibling path for ``source`` that does not exist yet, in
    the form ``stem (copy).ext``, ``stem (copy 2).ext``, …"""
    parent = source.parent
    stem = source.stem
    suffix = source.suffix
    candidate = parent / f"{stem} (copy){suffix}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = parent / f"{stem} (copy {n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _partition_delete_batch(
    paths: Iterable[str],
    images: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    """Split a delete batch into (viewer-list files, folders, loose files).

    Viewer-list files soft-delete in memory (no disk I/O until shutdown),
    folders soft-delete through the app Recycle Bin, and loose files are the
    only group that needs OS-trash calls right away.
    """
    image_set = set(images)
    in_list: list[str] = []
    folders: list[str] = []
    loose: list[str] = []
    for path in paths:
        if Path(path).is_dir():
            folders.append(path)
        elif path in image_set:
            in_list.append(path)
        else:
            loose.append(path)
    return in_list, folders, loose


def _dedupe_paths(paths: Iterable[str]) -> list[str]:
    """Order-preserving de-duplication of paths, dropping empty strings.

    The selection model yields one index per selected row but a path can
    repeat (e.g. the same file reachable through an expanded + collapsed
    branch); the batch ops need each path exactly once.
    """
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out
