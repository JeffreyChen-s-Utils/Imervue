"""Sorting layer for the file tree.

``QFileSystemModel`` can only sort by its four built-in columns (name, size,
type, modified) — it has no creation-date column. :class:`FileTreeSortProxy`
wraps the tree's model in a ``QSortFilterProxyModel`` whose ``lessThan``
understands a named sort key (``name`` / ``size`` / ``modified`` /
``created``), keeping directories grouped before files in both sort orders
like the native model does on Windows.

The proxy also forwards the ``QFileSystemModel``-flavoured API the rest of
the app calls on the tree model (``setRootPath``, path-based ``index``,
``filePath`` …), mapping indexes across the proxy boundary, so call sites
never need to know a proxy exists.

``dirs_first_precedence`` and ``file_sort_value`` are pure and unit-tested
without a Qt model.
"""
from __future__ import annotations

from PySide6.QtCore import QCollator, QModelIndex, QSortFilterProxyModel, Qt

TREE_SORT_KEYS = ("name", "modified", "created", "size")
DEFAULT_TREE_SORT_KEY = "name"


def normalize_sort_key(key: str | None) -> str:
    """Clamp *key* to a supported tree sort key."""
    return key if key in TREE_SORT_KEYS else DEFAULT_TREE_SORT_KEY


def dirs_first_precedence(left_is_dir: bool, right_is_dir: bool,
                          ascending: bool) -> bool | None:
    """Grouping decision for a mixed dir/file pair; ``None`` for same kind.

    ``QSortFilterProxyModel`` inverts ``lessThan`` results for a descending
    sort, so to keep directories on top in BOTH orders (Explorer style, and
    what ``QFileSystemModel`` does natively) the returned precedence must be
    pre-inverted for descending.
    """
    if left_is_dir == right_is_dir:
        return None
    return left_is_dir if ascending else not left_is_dir


def file_sort_value(info, key: str):
    """Comparable sort value for *info* under *key*; ``None`` for ``name``.

    *info* is ``QFileInfo``-shaped (``size`` / ``lastModified`` /
    ``birthTime``). A missing birth time (filesystem doesn't record one)
    falls back to the modified time so "created" still yields a stable,
    sensible order. ``name`` returns ``None`` — the caller's locale-aware
    filename comparison is both the key and the tie-breaker there.
    """
    if key == "size":
        return info.size()
    if key == "modified":
        return info.lastModified()
    if key == "created":
        birth = info.birthTime()
        return birth if birth.isValid() else info.lastModified()
    return None


class FileTreeSortProxy(QSortFilterProxyModel):
    """Sort proxy + ``QFileSystemModel``-compatible facade for the file tree."""

    def __init__(self, source, parent=None) -> None:
        super().__init__(parent)
        self._sort_key = DEFAULT_TREE_SORT_KEY
        # Locale-aware, numeric-mode name comparison (img2 < img10), matching
        # what users expect from Explorer.
        self._collator = QCollator()
        self._collator.setNumericMode(True)
        self._collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        source.setParent(self)
        self.setSourceModel(source)
        # Forward the signal object itself so existing
        # ``model.directoryLoaded.connect(...)`` call sites keep working.
        self.directoryLoaded = source.directoryLoaded

    # -- sorting -------------------------------------------------------

    def sort_key(self) -> str:
        return self._sort_key

    def set_sort_key(self, key: str) -> None:
        key = normalize_sort_key(key)
        if key != self._sort_key:
            self._sort_key = key
            self.invalidate()

    def lessThan(self, left, right) -> bool:  # noqa: N802 - Qt override
        src = self.sourceModel()
        left_info = src.fileInfo(left)
        right_info = src.fileInfo(right)
        ascending = self.sortOrder() == Qt.SortOrder.AscendingOrder
        grouped = dirs_first_precedence(
            left_info.isDir(), right_info.isDir(), ascending)
        if grouped is not None:
            return grouped
        left_val = file_sort_value(left_info, self._sort_key)
        right_val = file_sort_value(right_info, self._sort_key)
        if left_val is not None and left_val != right_val:
            return left_val < right_val
        return self._collator.compare(
            left_info.fileName(), right_info.fileName()) < 0

    # -- QFileSystemModel facade ----------------------------------------

    def index(self, row_or_path, column: int = 0, parent=None):
        """Support the path overload of ``QFileSystemModel.index``."""
        if isinstance(row_or_path, str):
            return self.mapFromSource(
                self.sourceModel().index(row_or_path, column))
        return super().index(
            row_or_path, column,
            parent if parent is not None else QModelIndex())

    def filePath(self, index) -> str:  # noqa: N802 - mirrors QFileSystemModel
        return self.sourceModel().filePath(self.mapToSource(index))

    def fileIcon(self, index):  # noqa: N802 - mirrors QFileSystemModel
        return self.sourceModel().fileIcon(self.mapToSource(index))

    def isDir(self, index) -> bool:  # noqa: N802 - mirrors QFileSystemModel
        return self.sourceModel().isDir(self.mapToSource(index))

    def setRootPath(self, path: str):  # noqa: N802 - mirrors QFileSystemModel
        return self.mapFromSource(self.sourceModel().setRootPath(path))

    def rootPath(self) -> str:  # noqa: N802 - mirrors QFileSystemModel
        return self.sourceModel().rootPath()

    def setNameFilters(self, filters) -> None:  # noqa: N802 - mirrors QFileSystemModel
        self.sourceModel().setNameFilters(filters)

    def setNameFilterDisables(self, enable: bool) -> None:  # noqa: N802 - mirrors QFileSystemModel
        self.sourceModel().setNameFilterDisables(enable)

    # -- FolderThumbnailModel facade --------------------------------------

    def set_icon_size(self, px: int) -> None:
        self.sourceModel().set_icon_size(px)

    def icon_size(self) -> int:
        return self.sourceModel().icon_size()

    def clear_missing_previews(self) -> None:
        self.sourceModel().clear_missing_previews()
