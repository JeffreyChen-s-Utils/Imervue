"""Track lazy reads, stale results, and bounded retries."""

from __future__ import annotations
from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import QImage

from Imervue.gui.image_list_rows import _RowMeta
from Imervue.gui.image_list_worker import _ThumbWorker
from Imervue.gui.image_list_values import _MAX_THUMB_RETRIES


class ImageListFetchMixin:
    """Track lazy reads, stale results, and bounded retries."""

    def refetch(self, paths) -> None:
        """Read *paths* again: another program rewrote, removed or restored them.

        Each row keeps its old thumbnail until the new read lands, and is read
        again only once it is on screen. A read already under way may have
        seen the old file, so its result is dropped and the row read afresh.
        """
        wanted = set(paths)
        for i, row in enumerate(self._rows):
            if row.path not in wanted:
                continue
            self._retry.pop(row.path, None)
            if row.path in self._in_flight:
                self._stale.add(row.path)
                continue
            row.fetched = False
            self.dataChanged.emit(
                self.index(i, self.COL_THUMB),
                self.index(i, self.COL_THUMB),
                [Qt.ItemDataRole.DecorationRole],
            )

    def _ensure_fetched(self, row: _RowMeta) -> None:
        if row.fetched or row.path in self._in_flight:
            return
        self._in_flight.add(row.path)
        worker = _ThumbWorker(row.path)
        worker.signals.done.connect(self._on_fetched)
        self._pool.start(worker)

    def _row_index(self, path: str) -> tuple[int, _RowMeta] | None:
        for i, row in enumerate(self._rows):
            if row.path == path:
                return i, row
        return None

    def _bump_retry(self, path: str) -> bool:
        """Increment *path*'s retry counter; True while still under the cap."""
        count = self._retry.get(path, 0)
        if count >= _MAX_THUMB_RETRIES:
            return False
        self._retry[path] = count + 1
        return True

    def _on_fetched(
        self, path: str, img: QImage, w: int, h: int, size_kb: float, mtime: float, ok: bool
    ) -> None:
        self._in_flight.discard(path)
        found = self._row_index(path)
        if found is None:
            return
        i, row = found
        if path in self._stale:
            # Read before another program saved over the file: read it again.
            self._stale.discard(path)
            self._ensure_fetched(row)
            return
        if not ok and self._bump_retry(path):
            # Transient stat/decode failure (file mid-move/locked) — retry
            # instead of caching a permanent placeholder.
            self._ensure_fetched(row)
            return
        self._retry.pop(path, None)
        self._apply_row_meta(row, self._pixmap_from_image(img), w, h, size_kb, mtime, ok)
        self.dataChanged.emit(
            self.index(i, 0),
            self.index(i, self.COL_COUNT - 1),
            [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.DisplayRole],
        )
