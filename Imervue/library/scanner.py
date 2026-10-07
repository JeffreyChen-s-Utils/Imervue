"""
Background scanner — walks library roots and populates the SQLite index.

Runs in a QThread; emits progress signals so the UI can show a status bar.
Rescans are incremental: a file whose mtime and size match its row is skipped
without being opened, unless the scan wants a pHash the row lacks. The files
that do need reading are decoded on a small thread pool (Pillow and NumPy
release the GIL) with the database lock free, and each chunk's rows are then
written in one transaction.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from Imervue.image.dimensions import image_dimensions
from Imervue.image.formats import ensure_pillow_opener
from Imervue.library import image_index
from Imervue.library.maintenance import scan_image_files
from Imervue.library.bloom_filter import BloomFilter, fingerprint
from Imervue.library.phash import compute_phash
from Imervue.system.job_state import JobState

logger = logging.getLogger("Imervue.library.scanner")

# Files indexed per DB transaction during a bulk scan. Large enough to amortise
# commit overhead, small enough to keep progress durable and transactions short.
_SCAN_COMMIT_CHUNK = 256
# Decoding threads at most; one core is always left for the UI.
_MAX_PROBE_WORKERS = 8
_PROGRESS_EVERY = 10


def probe_workers(cpu_count: int | None = None) -> int:
    """Threads that decode files at once: every core but one, between 1 and 8."""
    cpus = os.cpu_count() if cpu_count is None else cpu_count
    return max(1, min(_MAX_PROBE_WORKERS, (cpus or 1) - 1))


def _iter_images(root: str) -> Iterable[Path]:
    # The same walk Library Maintenance diffs against, so a file it reports as
    # new is one a rescan indexes.
    return (Path(p) for p in scan_image_files([root]))


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
    path: Path, stat_result, bloom: BloomFilter | None, *, need_phash: bool = False,
) -> bool:
    """``True`` when the bloom filter says this file is *probably*
    already indexed AND an exact-row check confirms mtime + size
    match. The two-stage check keeps bloom-filter false positives
    from making us miss a real update. With *need_phash* a row
    indexed without a pHash is not skipped, so the scan fills it in."""
    if bloom is None:
        return False
    fp = fingerprint(str(path), stat_result.st_mtime, stat_result.st_size)
    if fp not in bloom:
        return False
    # Bloom says "maybe" — confirm with an exact lookup.
    row = image_index.get_image(str(path))
    if row is None or (need_phash and row["phash"] is None):
        return False
    return (
        row["mtime"] is not None
        and row["size"] is not None
        and float(row["mtime"]) == float(stat_result.st_mtime)
        and int(row["size"]) == int(stat_result.st_size)
    )


@dataclass(frozen=True)
class ScanRow:
    """What one file contributes to the index: its stat, and its size and pHash when read."""

    path: str
    size: int
    mtime: float
    width: int | None = None
    height: int | None = None
    phash: int | None = None


def _probe(path: Path, stat_result, *, with_phash: bool) -> ScanRow:
    """Read what the index stores for *path*; touches no database.

    With ``with_phash`` the file is decoded for its size and pHash; an
    unreadable file still yields a row, without them.
    """
    width = height = None
    ensure_pillow_opener(path.suffix)   # compute_phash reads HEIC / JXL only with the codec
    if with_phash:
        width, height = image_dimensions(path) or (None, None)
    phash = compute_phash(path) if with_phash else None
    return ScanRow(str(path), stat_result.st_size, stat_result.st_mtime, width, height, phash)


def _store(row: ScanRow) -> None:
    """Write *row*; its size and pHash replace the old ones, which describe the old content."""
    image_index.upsert_image(row.path, size=row.size, mtime=row.mtime)
    image_index.set_decoded_fields(row.path, width=row.width, height=row.height, phash=row.phash)


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
    if _can_skip_via_bloom(path, stat, bloom, need_phash=with_phash):
        return False
    _store(_probe(path, stat, with_phash=with_phash))
    return True


@dataclass(frozen=True)
class _Pending:
    """A file of the current chunk that must be read: its place in the scan and its stat."""

    position: int
    path: Path
    stat: os.stat_result


class LibraryScanner(QObject):
    """Headless scanner — emit progress / done without owning a thread directly."""

    progress = Signal(int, int, str)   # (current, total, path)
    done = Signal(int)                 # total_indexed
    error = Signal(str)

    def __init__(self, roots: list[str], *, with_phash: bool = True,
                 paths: list[str] | None = None):
        super().__init__()
        self._roots = list(roots)
        self._with_phash = with_phash
        self._cancel = False
        self._reported = 0
        self._exact_paths = paths
        self.job_state = JobState()

    def cancel(self) -> None:
        self._cancel = True
        self.job_state.request_cancel()

    def run(self) -> None:
        try:
            paths = self._discover_paths()
            self.job_state.set_items([str(path) for path in paths])
            total = len(paths)
            # Hydrate the skip-bloom once before walking — on a
            # re-scan of an unchanged library this lets ~all files
            # short-circuit without a SQL upsert or pHash decode.
            bloom = _build_skip_bloom()
            self._scan_paths(paths, total, bloom)
            self.done.emit(total)
        except Exception as exc:
            logger.exception("library scan failed")
            self.job_state.finish(error=str(exc) or type(exc).__name__)
            self.error.emit(str(exc))
        finally:
            self.job_state.finish()

    def _discover_paths(self) -> list[Path]:
        if self._exact_paths is not None:
            return [Path(path) for path in self._exact_paths]
        return [path for root in self._roots if Path(root).is_dir() for path in _iter_images(root)]

    def _cancelled(self) -> bool:
        return self._cancel or self.job_state.cancelled

    def _scan_paths(self, paths: list[Path], total: int, bloom) -> None:
        """Index *paths*, committing one transaction per chunk so a large
        first scan isn't N separate commits while progress stays durable."""
        with ThreadPoolExecutor(max_workers=probe_workers(),
                                thread_name_prefix="library-probe") as pool:
            for start in range(0, total, _SCAN_COMMIT_CHUNK):
                if self._cancelled():
                    return
                chunk = paths[start:start + _SCAN_COMMIT_CHUNK]
                self._scan_chunk(pool, chunk, start, total, bloom)

    def _scan_chunk(self, pool: Executor, chunk: list[Path], start: int, total: int,
                    bloom) -> None:
        """Probe the chunk's changed files on *pool*, then write their rows in one batch."""
        pending = self._changed(chunk, start, bloom)
        rows: list[ScanRow] = []
        for item, row in zip(pending, pool.map(self._probe_unless_cancelled, pending),
                             strict=True):
            if row is not None:
                rows.append(row)
            self._report(item.position + 1, total, item.path)
        with image_index.write_batch():
            for row in rows:
                _store(row)
        for row in rows:
            self.job_state.record(row.path)
        if chunk and not self._cancelled():
            self._report(start + len(chunk), total, chunk[-1], force=True)

    def _changed(self, chunk: list[Path], start: int, bloom) -> list[_Pending]:
        """The chunk's files that are new, changed, or missing the pHash this scan wants."""
        pending = []
        for offset, path in enumerate(chunk):
            try:
                stat = path.stat()
            except OSError as exc:
                self.job_state.record(str(path), error=str(exc))
                continue
            if not _can_skip_via_bloom(path, stat, bloom, need_phash=self._with_phash):
                pending.append(_Pending(start + offset, path, stat))
            else:
                self.job_state.record(str(path))
        return pending

    def _probe_unless_cancelled(self, item: _Pending) -> ScanRow | None:
        if self._cancelled():
            return None
        return _probe(item.path, item.stat, with_phash=self._with_phash)

    def _report(self, current: int, total: int, path: Path, *, force: bool = False) -> None:
        """Emit progress every few files, at each chunk's end (*force*) and at the last file."""
        due = force or current % _PROGRESS_EVERY == 0 or current == total
        if current > self._reported and due:
            self._reported = current
            self.progress.emit(current, total, str(path))


class LibraryScanThread(QThread):
    """QThread wrapper around LibraryScanner."""

    progress = Signal(int, int, str)
    done = Signal(int)
    error = Signal(str)

    def __init__(self, roots: list[str], *, with_phash: bool = True, parent=None,
                 paths: list[str] | None = None):
        super().__init__(parent)
        self._scanner = LibraryScanner(roots, with_phash=with_phash, paths=paths)
        self.job_state = self._scanner.job_state
        self._scanner.progress.connect(self.progress)
        self._scanner.done.connect(self.done)
        self._scanner.error.connect(self.error)

    def cancel(self) -> None:
        self._scanner.cancel()

    def stop(self) -> None:
        """WorkerHost cancellation hook; only sets the shared cancellation flag."""
        self.cancel()

    def run(self) -> None:
        self._scanner.run()
