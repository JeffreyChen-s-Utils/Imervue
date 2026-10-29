"""Library maintenance — reconcile the SQLite index against the filesystem.

Finds index rows whose file is gone ("missing") and image files on disk that
the index has never seen ("new"), so the library can be kept honest as files
move around. The set-diff is pure and unit-tested; the scan/prune orchestration
touches the filesystem and the index.
"""
from __future__ import annotations

import os
from collections.abc import Iterable

from Imervue.image.formats import STILL_IMAGE_EXTENSIONS
from Imervue.system.image_listing import list_images


def diff_index_vs_fs(indexed: Iterable[str], fs: Iterable[str]) -> dict:
    """Return ``{"missing": [...], "new": [...]}`` comparing index vs disk."""
    indexed_set, fs_set = set(indexed), set(fs)
    return {
        "missing": sorted(indexed_set - fs_set),
        "new": sorted(fs_set - indexed_set),
    }


def scan_image_files(folders: Iterable[str]) -> list[str]:
    """Recursively collect image files under *folders*, hidden files and folders left out.

    So indexing a drive's root skips ``$RECYCLE.BIN`` and a Mac's ``.Trashes``.
    """
    return [path for folder in folders
            for path in list_images(folder, STILL_IMAGE_EXTENSIONS, recursive=True)]


def _readable_roots(folders: Iterable[str]) -> list[str]:
    roots = []
    for folder in folders:
        try:
            with os.scandir(folder):
                roots.append(os.path.normcase(os.path.abspath(folder)))
        except OSError:
            continue
    return roots


def _confirmed_missing(path: str, roots: list[str]) -> bool:
    candidate = os.path.normcase(os.path.abspath(path))
    in_scope = False
    for root in roots:
        try:
            if os.path.commonpath((candidate, root)) == root:
                in_scope = True
                break
        except ValueError:  # Paths on different drives cannot share a root.
            continue
    if not in_scope:
        return False
    try:
        os.lstat(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def run_maintenance(folders: Iterable[str], *, prune: bool = False) -> dict:
    """Diff the index against *folders*; optionally prune missing index rows."""
    from Imervue.library import image_index
    folders = tuple(folders)
    diff = diff_index_vs_fs(image_index.all_image_paths(), scan_image_files(folders))
    roots = _readable_roots(folders)
    diff["missing"] = [path for path in diff["missing"] if _confirmed_missing(path, roots)]
    if prune:
        for path in diff["missing"]:
            image_index.delete_image(path)
    return {
        "missing": len(diff["missing"]),
        "new": len(diff["new"]),
        "pruned": len(diff["missing"]) if prune else 0,
        "details": diff,
    }
