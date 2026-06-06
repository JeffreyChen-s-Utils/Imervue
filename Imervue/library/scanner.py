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
from Imervue.library.bloom_filter import BloomFilter, fingerprint
from Imervue.library.phash import compute_phash

logger = logging.getLogger("Imervue.library.scanner")

# Files indexed per DB transaction during a bulk scan. Large enough to amortise
# commit overhead, small enough to keep progress durable and transactions short.
_SCAN_COMMIT_CHUNK = 256

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


def _build_skip_bloom() -> BloomFilter:
    """Hydrate a bloom filter from the existing catalog so the
    scanner can short-circuit unchanged files without hitting SQL
    or recomputing pHash."""
    count = max(1024, image_index.count_images())
    bloom = BloomFilter(expected_items=count)
    for path, mtime, size in image_index.iter_image_fingerprints():
        bloom.add(fingerprint(path, mtime, size))
    return bloom


def _can_skip_via_bloom(
    path: Path, stat_result, bloom: BloomFilter | None,
) -> bool:
    """``True`` when the bloom filter says this file is *probably*
    already indexed AND an exact-row check confirms mtime + size
    match. The two-stage check keeps bloom-filter false positives
    from making us miss a real update."""
    if bloom is None:
        return False
    fp = fingerprint(str(path), stat_result.st_mtime, stat_result.st_size)
    if fp not in bloom:
        return False
    # Bloom says "maybe" — confirm with an exact lookup.
    row = image_index.get_image(str(path))
    if row is None:
        return False
    return (
        row["mtime"] is not None
        and row["size"] is not None
        and float(row["mtime"]) == float(stat_result.st_mtime)
        and int(row["size"]) == int(stat_result.st_size)
    )


def _index_one(
    path: Path, *, with_phash: bool, bloom: BloomFilter | None = None,
) -> bool:
    """Index a single file. Returns ``True`` when the file was
    upserted, ``False`` when the bloom filter let us skip it
    (caller uses the return value for progress accounting)."""
    try:
        stat = path.stat()
    except OSError:
        return False
    if _can_skip_via_bloom(path, stat, bloom):
        return False
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
    return True


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
            # Hydrate the skip-bloom once before walking — on a
            # re-scan of an unchanged library this lets ~all files
            # short-circuit without a SQL upsert or pHash decode.
            bloom = _build_skip_bloom()
            self._scan_paths(paths, total, bloom)
            self.done.emit(total)
        except Exception as exc:  # noqa: BLE001
            logger.exception("library scan failed")
            self.error.emit(str(exc))

    def _scan_paths(self, paths: list[Path], total: int, bloom) -> None:
        """Index *paths*, committing one transaction per chunk so a large
        first scan isn't N separate commits while progress stays durable."""
        for start in range(0, total, _SCAN_COMMIT_CHUNK):
            if self._cancel:
                return
            with image_index.write_batch():
                for offset, p in enumerate(paths[start:start + _SCAN_COMMIT_CHUNK]):
                    if self._cancel:
                        break
                    _index_one(p, with_phash=self._with_phash, bloom=bloom)
                    i = start + offset + 1
                    if i % 10 == 0 or i == total:
                        self.progress.emit(i, total, str(p))


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
