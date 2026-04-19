"""
Background scanner — walks library roots and populates the SQLite index.

Runs in a QThread; emits progress signals so the UI can show a status bar.
Per-image work (stat + pHash) is cheap enough to do sequentially; if the root
has tens of thousands of images we throttle by yielding every N files.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from Imervue.library import image_index
from Imervue.library.phash import compute_phash

logger = logging.getLogger("Imervue.library.scanner")

_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
    ".gif", ".apng", ".svg",
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
}


def _iter_images(root: str) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in _IMAGE_EXTS:
                yield p


def _index_one(path: Path, *, with_phash: bool) -> None:
    try:
        stat = path.stat()
    except OSError:
        return
    width = height = None
    if with_phash:
        try:
            from PIL import Image
            with Image.open(path) as im:
                width, height = im.size
        except Exception:  # noqa: BLE001, S110  # nosec B110 - size nice-to-have; skip PIL failure
            pass
    phash = compute_phash(path) if with_phash else None
    image_index.upsert_image(
        str(path),
        size=stat.st_size,
        mtime=stat.st_mtime,
        width=width,
        height=height,
        phash=phash,
    )


class LibraryScanner(QObject):
    """Headless scanner — emit progress / done without owning a thread directly."""

    progress = Signal(int, int, str)   # (current, total, path)
    done = Signal(int)                 # total_indexed
    error = Signal(str)

    def __init__(self, roots: list[str], *, with_phash: bool = True):
        super().__init__()
        self._roots = list(roots)
        self._with_phash = with_phash
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            paths: list[Path] = []
            for root in self._roots:
                if not Path(root).is_dir():
                    continue
                paths.extend(_iter_images(root))
            total = len(paths)
            for i, p in enumerate(paths, start=1):
                if self._cancel:
                    break
                _index_one(p, with_phash=self._with_phash)
                if i % 10 == 0 or i == total:
                    self.progress.emit(i, total, str(p))
            self.done.emit(total)
        except Exception as exc:  # noqa: BLE001
            logger.exception("library scan failed")
            self.error.emit(str(exc))


class LibraryScanThread(QThread):
    """QThread wrapper around LibraryScanner."""

    progress = Signal(int, int, str)
    done = Signal(int)
    error = Signal(str)

    def __init__(self, roots: list[str], *, with_phash: bool = True, parent=None):
        super().__init__(parent)
        self._scanner = LibraryScanner(roots, with_phash=with_phash)
        self._scanner.progress.connect(self.progress)
        self._scanner.done.connect(self.done)
        self._scanner.error.connect(self.error)

    def cancel(self) -> None:
        self._scanner.cancel()

    def run(self) -> None:
        self._scanner.run()
