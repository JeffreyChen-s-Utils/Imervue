"""Folder listing for the viewer: which entries it lists, the user's sort order
and the progressive scan worker.

Split out of :mod:`image_loader`, which re-exports every name here.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QRunnable, Signal, QObject

from Imervue.system.hidden_files import is_hidden
from Imervue.system.natural_sort import natural_key
from Imervue.image.formats import VIEWER_EXTENSIONS


class _FolderScanSignals(QObject):
    batch = Signal(str, list)
    finished = Signal(str, list)


def _is_listed(entry: os.DirEntry) -> bool:
    """A folder entry the viewer lists: a file it opens that is not hidden (``hidden_files``)."""
    return (entry.is_file(follow_symlinks=False)
            and os.path.splitext(entry.name)[1].lower() in VIEWER_EXTENSIONS
            and not is_hidden(entry))


class FolderScanWorker(QRunnable):
    """Scan a folder in chunks so very large folders can appear progressively."""

    def __init__(self, folder: str, batch_size: int = 256):
        super().__init__()
        self.folder = folder
        self.batch_size = max(32, int(batch_size))
        self.signals = _FolderScanSignals()
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        import os
        found: list[str] = []
        batch: list[str] = []
        try:
            with os.scandir(self.folder) as it:  # NOSONAR - user-selected local folder
                for entry in it:
                    if self._abort:
                        return
                    if not _is_listed(entry):
                        continue
                    batch.append(entry.path)
                    found.append(entry.path)
                    if len(batch) >= self.batch_size:
                        self.signals.batch.emit(self.folder, _sort_for_user(batch))
                        batch = []
        except OSError:
            self.signals.finished.emit(self.folder, [])
            return
        if batch and not self._abort:
            self.signals.batch.emit(self.folder, _sort_for_user(batch))
        if not self._abort:
            self.signals.finished.emit(self.folder, _sort_for_user(found))


# Sorts the directory listing already answers: DirEntry.stat() comes free with
# os.scandir on Windows (FindNextFile returns times and size), where a stat per
# path cost a system call each - 5000 files sorted by date took 5x longer.
_STAT_SORT_KEYS = {
    "modified": lambda st: st.st_mtime,
    "size": lambda st: st.st_size,
    "created": lambda st: getattr(st, "st_birthtime", st.st_ctime),
}


def _stat_value(entry, key) -> float:
    try:
        return key(entry.stat(follow_symlinks=False))
    except OSError:
        return 0


def _scan_images(directory: str, sort_by: str = "name", ascending: bool = True) -> list[str]:
    """
    快速掃描資料夾中的圖片，直接用使用者選定的排序方式一次排完（不再先 sort by name 再 re-sort）。
    Default arguments preserve the historical behaviour (alphabetical ascending)
    so external callers that don't care about user settings — the main window's
    folder refresh and the unit tests — keep getting the same result.
    """
    import os
    entries = []
    try:
        # Desktop viewer: *directory* is the user's own local folder pick
        # (file-open dialog / breadcrumb), not untrusted remote input — no
        # privilege boundary is crossed, so the taint warning is a false positive.
        with os.scandir(directory) as it:  # NOSONAR
            entries = [entry for entry in it if _is_listed(entry)]
    except OSError:
        return []

    stat_key = _STAT_SORT_KEYS.get(sort_by)
    if stat_key is not None:
        entries.sort(key=lambda entry: _stat_value(entry, stat_key), reverse=not ascending)
        return [entry.path for entry in entries]
    result = [entry.path for entry in entries]
    if sort_by == "name":
        # Fast default path — avoid the import of sort_menu for the common case.
        result.sort(key=lambda p: natural_key(os.path.basename(p)), reverse=not ascending)
    else:
        from Imervue.menu.sort_menu import _SORT_KEYS, _sort_key_name
        key_fn = _SORT_KEYS.get(sort_by, _sort_key_name)
        result.sort(key=key_fn, reverse=not ascending)
    return result


# Sorts that open every file's header (its size, its EXIF date): worth the cache.
_HEADER_SORTS = frozenset({"resolution", "taken"})


def _scan_images_for_user(directory: str) -> list[str]:
    """Scan + sort a folder using the user's current sort settings (single pass)."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    sort_by = user_setting_dict.get("sort_by", "name")
    ascending = user_setting_dict.get("sort_ascending", True)
    if sort_by not in _HEADER_SORTS:
        # Scanning is the fast path here: the cache checks every listed file
        # still exists, one system call each, while scandir lists them in
        # batches (5000 files by name: 38 ms scanned, 349 ms from the cache).
        return _scan_images(directory, sort_by=sort_by, ascending=ascending)
    from Imervue.image import folder_index
    cached = folder_index.load(directory, sort_by=sort_by, ascending=ascending)
    if cached is not None:
        return cached
    images = _scan_images(
        directory,
        sort_by=sort_by,
        ascending=ascending,
    )
    folder_index.save(directory, images, sort_by=sort_by, ascending=ascending)
    return images


def _sort_for_user(paths: list[str]) -> list[str]:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    sort_by = user_setting_dict.get("sort_by", "name")
    ascending = user_setting_dict.get("sort_ascending", True)
    result = list(paths)
    if sort_by == "name":
        result.sort(key=lambda p: natural_key(os.path.basename(p)), reverse=not ascending)
    else:
        from Imervue.menu.sort_menu import _SORT_KEYS, _sort_key_name
        result.sort(
            key=_SORT_KEYS.get(sort_by, _sort_key_name),
            reverse=not ascending,
        )
    return result
