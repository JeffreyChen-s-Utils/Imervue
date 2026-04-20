"""
圖片清單檢視
Image list view — QTableView alternative to the tile grid.

Columns: thumbnail · filename · resolution · size · type · modified.
Double-click opens deep zoom in the GPU viewer. Columns are sortable
and the view uses on-demand metadata fetching to stay responsive for
large folders.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, QSize, QThreadPool, QRunnable,
    Signal, QObject,
)
from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import (
    QTableView, QHeaderView, QAbstractItemView, QStyledItemDelegate,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


_THUMB_SIZE = 48


@dataclass
class _RowMeta:
    path: str
    size_kb: float | None = None
    width: int | None = None
    height: int | None = None
    mtime: float | None = None
    icon: QIcon | None = None
    fetched: bool = False


class _ThumbWorkerSignals(QObject):
    done = Signal(str, QPixmap, int, int, float, float)  # path, pm, w, h, size_kb, mtime


class _ThumbWorker(QRunnable):
    """Fetch file stat + a scaled thumbnail off the UI thread."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.signals = _ThumbWorkerSignals()

    def run(self) -> None:
        try:
            stat = os.stat(self.path)
            size_kb = stat.st_size / 1024
            mtime = stat.st_mtime
        except OSError:
            return

        try:
            with Image.open(self.path) as src:
                w, h = src.size
                src.thumbnail((_THUMB_SIZE, _THUMB_SIZE), Image.Resampling.LANCZOS)
                im = src.convert("RGBA")
                data = im.tobytes("raw", "RGBA")
                from PySide6.QtGui import QImage
                qimg = QImage(data, im.width, im.height, QImage.Format.Format_RGBA8888)
                pm = QPixmap.fromImage(qimg.copy())
        except Exception:
            pm = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
            pm.fill(QColor(40, 40, 40))
            w = h = 0

        self.signals.done.emit(self.path, pm, w, h, size_kb, mtime)


class ImageListModel(QAbstractTableModel):
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

    def __init__(self, paths: list[str] | None = None):
        super().__init__()
        self._rows: list[_RowMeta] = [_RowMeta(p) for p in (paths or [])]
        self._pool = QThreadPool.globalInstance()
        self._in_flight: set[str] = set()

    # --- QAbstractItemModel API ---
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else self.COL_COUNT

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        lang = language_wrapper.language_word_dict
        keys = {
            self.COL_THUMB: ("list_col_thumb", "Preview"),
            self.COL_LABEL: ("list_col_label", "Label"),
            self.COL_RATING: ("list_col_rating", "Rating"),
            self.COL_NAME: ("list_col_name", "Name"),
            self.COL_RES: ("list_col_resolution", "Resolution"),
            self.COL_SIZE: ("list_col_size", "Size"),
            self.COL_TYPE: ("list_col_type", "Type"),
            self.COL_MTIME: ("list_col_modified", "Modified"),
        }
        key, fallback = keys[section]
        return lang.get(key, fallback)

    @staticmethod
    def _label_value(row) -> str:
        from Imervue.user_settings.color_labels import get_color_label
        return (get_color_label(row.path) or "").title()

    def _resolution_value(self, row) -> str:
        self._ensure_fetched(row)
        if row.width and row.height:
            return f"{row.width}\u00d7{row.height}"
        return ""

    def _size_value(self, row) -> str:
        self._ensure_fetched(row)
        if row.size_kb is None:
            return ""
        return _fmt_size(row.size_kb)

    def _mtime_value(self, row) -> str:
        self._ensure_fetched(row)
        if row.mtime is None:
            return ""
        return datetime.fromtimestamp(row.mtime).strftime("%Y-%m-%d %H:%M")

    def _display_value(self, row, col: int):
        handlers = {
            self.COL_LABEL: self._label_value,
            self.COL_RATING: lambda r: _format_rating(_rating_for(r.path)),
            self.COL_NAME: lambda r: Path(r.path).name,
            self.COL_RES: self._resolution_value,
            self.COL_SIZE: self._size_value,
            self.COL_TYPE: lambda r: Path(r.path).suffix.lstrip(".").upper() or "",
            self.COL_MTIME: self._mtime_value,
        }
        handler = handlers.get(col)
        return handler(row) if handler else ""

    def _background_value(self, row, col: int):
        if col != self.COL_LABEL:
            return None
        from Imervue.user_settings.color_labels import get_color_label, COLOR_RGB
        color = get_color_label(row.path)
        if color and color in COLOR_RGB:
            r, g, b = COLOR_RGB[color]
            return QColor(r, g, b, 200)
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return row.path
        if role == Qt.ItemDataRole.DecorationRole and col == self.COL_THUMB:
            self._ensure_fetched(row)
            return row.icon
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background_value(row, col)
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(row, col)
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and col in (self.COL_RES, self.COL_SIZE)
        ):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and col == self.COL_RATING
        ):
            return int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.path
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sort rows in-place by the chosen column.

        Uses already-fetched metadata where available; unfetched rows compare
        by path so they stay stable until their data arrives.
        """
        def _color_key(r):
            from Imervue.user_settings.color_labels import get_color_label, COLORS
            c = get_color_label(r.path)
            if c is None:
                return (1, "")  # Unlabelled sorts after labelled
            try:
                return (0, COLORS.index(c))
            except ValueError:
                return (1, c)

        key_funcs = {
            self.COL_NAME: lambda r: Path(r.path).name.lower(),
            self.COL_RES: lambda r: ((r.width or 0) * (r.height or 0)),
            self.COL_SIZE: lambda r: (r.size_kb or 0),
            self.COL_TYPE: lambda r: Path(r.path).suffix.lower(),
            self.COL_MTIME: lambda r: (r.mtime or 0),
            self.COL_THUMB: lambda r: Path(r.path).name.lower(),
            self.COL_LABEL: _color_key,
            self.COL_RATING: lambda r: _rating_for(r.path),
        }
        key = key_funcs.get(column, key_funcs[self.COL_NAME])
        reverse = order == Qt.SortOrder.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=key, reverse=reverse)
        self.layoutChanged.emit()

    # --- Public helpers ---
    def set_paths(self, paths: list[str]) -> None:
        self.beginResetModel()
        self._rows = [_RowMeta(p) for p in paths]
        self._in_flight.clear()
        self.endResetModel()

    def path_at(self, row: int) -> str | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].path
        return None

    # --- Lazy loading ---
    def _ensure_fetched(self, row: _RowMeta) -> None:
        if row.fetched or row.path in self._in_flight:
            return
        self._in_flight.add(row.path)
        worker = _ThumbWorker(row.path)
        worker.signals.done.connect(self._on_fetched)
        self._pool.start(worker)

    def _on_fetched(self, path: str, pm: QPixmap, w: int, h: int,
                    size_kb: float, mtime: float) -> None:
        self._in_flight.discard(path)
        for i, row in enumerate(self._rows):
            if row.path != path:
                continue
            row.width = w or None
            row.height = h or None
            row.size_kb = size_kb
            row.mtime = mtime
            row.icon = QIcon(pm)
            row.fetched = True
            top = self.index(i, 0)
            bot = self.index(i, self.COL_COUNT - 1)
            self.dataChanged.emit(top, bot, [
                Qt.ItemDataRole.DecorationRole,
                Qt.ItemDataRole.DisplayRole,
            ])
            break


_STAR_FILLED = "\u2605"
_STAR_EMPTY = "\u2606"
_RATING_MAX = 5


def _rating_for(path: str) -> int:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    ratings = user_setting_dict.get("image_ratings") or {}
    try:
        return int(ratings.get(path, 0))
    except (TypeError, ValueError):
        return 0


def _format_rating(rating: int) -> str:
    if rating <= 0:
        return ""
    rating = min(max(int(rating), 0), _RATING_MAX)
    return _STAR_FILLED * rating + _STAR_EMPTY * (_RATING_MAX - rating)


def _fmt_size(kb: float) -> str:
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB"
    return f"{kb:.1f} KB"


class _RowDelegate(QStyledItemDelegate):
    """Fixed 48-px row height for consistent thumbnail rendering."""

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), max(s.height(), _THUMB_SIZE + 4))


class ImageListView(QTableView):
    """QTableView configured for image browsing."""

    image_activated = Signal(str)  # emitted on double-click / Enter

    def __init__(self, main_window: ImervueMainWindow):
        super().__init__()
        self._main_window = main_window

        self._model = ImageListModel()
        self.setModel(self._model)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setHighlightSections(False)
        self.setItemDelegate(_RowDelegate(self))

        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.setColumnWidth(ImageListModel.COL_THUMB, 64)
        self.setColumnWidth(ImageListModel.COL_LABEL, 70)
        self.setColumnWidth(ImageListModel.COL_RATING, 86)
        self.setColumnWidth(ImageListModel.COL_NAME, 320)
        self.setColumnWidth(ImageListModel.COL_RES, 110)
        self.setColumnWidth(ImageListModel.COL_SIZE, 100)
        self.setColumnWidth(ImageListModel.COL_TYPE, 70)

        self.doubleClicked.connect(self._on_activate)

    # --- Public API ---
    def set_paths(self, paths: list[str]) -> None:
        self._model.set_paths(paths)

    def selected_paths(self) -> list[str]:
        return [
            self._model.path_at(idx.row())
            for idx in self.selectionModel().selectedRows()
            if self._model.path_at(idx.row())
        ]

    # --- Events ---
    def _on_activate(self, index: QModelIndex) -> None:
        path = self._model.path_at(index.row())
        if path:
            self.image_activated.emit(path)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            idx = self.currentIndex()
            if idx.isValid():
                path = self._model.path_at(idx.row())
                if path:
                    self.image_activated.emit(path)
                    return
        super().keyPressEvent(event)
