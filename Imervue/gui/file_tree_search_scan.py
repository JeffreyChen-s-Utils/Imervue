"""Stream filename matches under a folder without following reparse points.

Pure filesystem walk (no Qt): ``file_tree_search`` runs it on a worker thread.
"""
import os
import stat
from pathlib import Path
from threading import Event

from Imervue.image.formats import VIEWER_EXTENSIONS


class _FilenameSearch:
    def __init__(self, root, query, cancelled, emit_batch, batch_size, excluded):
        self.pending = [root]
        self.query = query.casefold()
        self.cancelled = cancelled
        self.emit_batch = emit_batch
        self.batch_size = batch_size
        self.excluded = excluded
        self.extensions = {ext.casefold() for ext in VIEWER_EXTENSIONS}
        self.batch = []
        self.unreadable = 0

    def run(self) -> int:
        while self.pending and not self.cancelled.is_set():
            self._scan_folder(self.pending.pop())
        if self.batch and not self.cancelled.is_set():
            self.emit_batch(self.batch)
        return self.unreadable

    def _scan_folder(self, folder: str) -> None:
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if self.cancelled.is_set():
                        break
                    try:
                        self._visit_entry(entry)
                    except OSError:
                        self.unreadable += 1
        except OSError:
            self.unreadable += 1

    def _visit_entry(self, entry: os.DirEntry) -> None:
        if entry.name.startswith(".") or os.path.normcase(entry.path) in self.excluded:
            return
        is_dir = entry.is_dir(follow_symlinks=False)
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        if attrs & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0):
            return
        reparse = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if is_dir and not entry.is_symlink() and not reparse:
            self.pending.append(entry.path)
        if self.query in entry.name.casefold() and (
            is_dir or Path(entry.name).suffix.casefold() in self.extensions
        ):
            self.batch.append(entry.path)
        if len(self.batch) >= self.batch_size:
            self.emit_batch(self.batch)
            self.batch = []


def scan_matches(root: str, query: str, cancelled: Event, emit_batch, *,
                 batch_size=100, excluded: frozenset[str] = frozenset()) -> int:
    """Stream matching folders/images without following filesystem reparse points."""
    return _FilenameSearch(root, query, cancelled, emit_batch, batch_size, excluded).run()
