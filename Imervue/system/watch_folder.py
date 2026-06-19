"""Watched-folder automation — apply an action to images as they arrive.

Watches a folder with a recursive ``watchdog.Observer`` (the same pattern as
:mod:`Imervue.system.file_tree_watcher`); when new image files appear, each is
handed to an injected *processor* callable on the UI thread. The viewer wires a
processor that assigns a chosen develop preset to the new file, giving a
hands-off ingest pipeline.

The new-file detection (extension filter + set-diff against what was already
seen) is pure and unit-tested; only the live Observer wiring needs Qt.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger("Imervue.watch_folder")

_DEBOUNCE_MS = 500
DEFAULT_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
    ".heic", ".heif", ".avif", ".jxl",
})


def is_image(path: str, extensions: Iterable[str] = DEFAULT_EXTENSIONS) -> bool:
    """True when *path* has an image extension in *extensions*."""
    return Path(path).suffix.lower() in set(extensions)


def scan_images(root: str, extensions: Iterable[str] = DEFAULT_EXTENSIONS) -> set[str]:
    """Return the set of image file paths directly inside *root*."""
    exts = set(extensions)
    try:
        return {
            entry.path for entry in os.scandir(root)
            if entry.is_file() and Path(entry.name).suffix.lower() in exts
        }
    except OSError:
        return set()


def select_new(seen: Iterable[str], current: Iterable[str]) -> list[str]:
    """Image paths present in *current* but not yet *seen*, sorted."""
    return sorted(set(current) - set(seen))


class WatchFolderService(QObject):
    """Run *processor* on each new image that lands in a watched folder."""

    processed = Signal(int)
    _changed = Signal()

    def __init__(
        self,
        processor: Callable[[str], None],
        extensions: Iterable[str] = DEFAULT_EXTENSIONS,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._processor = processor
        self._extensions = frozenset(extensions)
        self._seen: set[str] = set()
        self._observer = None
        self._root = ""

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._dispatch)
        self._changed.connect(self._debounce.start)

    @property
    def root(self) -> str:
        return self._root

    def start(self, root: str) -> bool:
        """Begin watching *root*; returns True once the observer is running."""
        self.stop()
        if not root or not Path(root).is_dir():
            return False
        self._seen = scan_images(root, self._extensions)
        if not self._start_observer(root):
            return False
        self._root = root
        return True

    def _start_observer(self, root: str) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.info("watchdog not installed — watched-folder automation disabled")
            return False
        emit = self._changed.emit

        class _Adapter(FileSystemEventHandler):
            def on_any_event(self, event):  # noqa: D401 — watchdog hook
                emit()

        try:
            observer = Observer()
            observer.schedule(_Adapter(), root, recursive=False)
            observer.daemon = True
            observer.start()
        except (OSError, RuntimeError) as exc:
            logger.warning("watched-folder observer failed on %s: %s", root, exc)
            return False
        self._observer = observer
        return True

    def stop(self) -> None:
        observer = self._observer
        self._observer = None
        self._root = ""
        if observer is None:
            return
        try:
            observer.stop()
            observer.join(timeout=1.0)
        except (RuntimeError, OSError) as exc:
            logger.debug("watched-folder observer stop raised: %s", exc)

    def _dispatch(self) -> None:
        if not self._root:
            return
        current = scan_images(self._root, self._extensions)
        new_paths = select_new(self._seen, current)
        self._seen = current
        for path in new_paths:
            try:
                self._processor(path)
            except Exception as exc:  # noqa: BLE001 — one bad file must not stop the watcher
                logger.warning("watched-folder processor failed on %s: %s", path, exc)
        if new_paths:
            self.processed.emit(len(new_paths))
