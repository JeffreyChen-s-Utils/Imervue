"""Library maintenance — reconcile the SQLite index against the filesystem.

Finds index rows whose file is gone ("missing") and image files on disk that
the index has never seen ("new"), so the library can be kept honest as files
move around. The set-diff is pure and unit-tested; the scan/prune orchestration
touches the filesystem and the index.
"""
from __future__ import annotations

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


def run_maintenance(folders: Iterable[str], *, prune: bool = False) -> dict:
    """Diff the index against *folders*; optionally prune missing index rows."""
    from Imervue.library import image_index
    diff = diff_index_vs_fs(image_index.all_image_paths(), scan_image_files(folders))
    if prune:
        for path in diff["missing"]:
            image_index.delete_image(path)
    return {
        "missing": len(diff["missing"]),
        "new": len(diff["new"]),
        "pruned": len(diff["missing"]) if prune else 0,
        "details": diff,
    }
