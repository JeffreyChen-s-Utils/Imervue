"""Qt table identity, reset operations, and image-path access."""

from __future__ import annotations
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QThreadPool,
)

from Imervue.gui.image_list_fetch import ImageListFetchMixin
from Imervue.gui.image_list_rows import ImageListRowsMixin, _RowMeta
from Imervue.gui.image_list_display import ImageListDisplayMixin
from Imervue.gui.image_list_cells import ImageListCellsMixin
from Imervue.gui.image_list_sort import ImageListSortMixin


class ImageListModel(
    ImageListFetchMixin,
    ImageListRowsMixin,
    ImageListDisplayMixin,
    ImageListCellsMixin,
    ImageListSortMixin,
    QAbstractTableModel,
):
    """Table model over a list of image paths.

    Metadata (thumbnail / dimensions / size / mtime) is loaded lazily via
    a thread pool; rows that haven't been fetched yet render with
    placeholder values and re-emit ``dataChanged`` when loading completes.
    """

    COL_THUMB = 0
    COL_LABEL = 1
    COL_RATING = 2
    COL_NAME = 3
    COL_RES = 4
    COL_SIZE = 5
    COL_TYPE = 6
    COL_MTIME = 7
    COL_COUNT = 8

    def __init__(self, paths: list[str] | None = None, metadata_index=None):
        super().__init__()
        self._metadata_index = metadata_index
        self._rows: list[_RowMeta] = [self._row_for_path(p) for p in (paths or [])]
        self._pool = QThreadPool.globalInstance()
        self._in_flight: set[str] = set()
        # path -> transient fetch-failure retry count (see _MAX_THUMB_RETRIES)
        self._retry: dict[str, int] = {}
        # In-flight reads that began before the file changed on disk (see refetch)
        self._stale: set[str] = set()

    # --- QAbstractItemModel API ---
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else self.COL_COUNT

    # --- Public helpers ---
    def set_paths(self, paths: list[str], metadata_index=None) -> None:
        if metadata_index is not None:
            self._metadata_index = metadata_index
        self.beginResetModel()
        self._rows = [self._row_for_path(p) for p in paths]
        self._in_flight.clear()
        self._retry.clear()
        self._stale.clear()
        self.endResetModel()

    def path_at(self, row: int) -> str | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].path
        return None

    def is_missing_at(self, row: int) -> bool:
        if 0 <= row < len(self._rows):
            return self._rows[row].missing
        return False

    # --- Lazy loading ---
