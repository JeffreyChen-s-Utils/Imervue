"""Sort cached rows and preserve persistent selection identity."""

from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import (
    Qt,
)
from Imervue.system.natural_sort import natural_key

from Imervue.gui.image_list_values import _rating_for


class ImageListSortMixin:
    """Sort cached rows and preserve persistent selection identity."""

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sort rows in-place by the chosen column.

        Uses already-fetched metadata; missing numeric values compare as zero.
        Names sort
        naturally (``img2`` before ``img10``), like the wall and the folder tree.
        Column -1 (no sort chosen) keeps the rows as they are.
        """
        if column < 0:
            return

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
            self.COL_NAME: lambda r: natural_key(Path(r.path).name),
            self.COL_RES: lambda r: (r.width or 0) * (r.height or 0),
            self.COL_SIZE: lambda r: r.size_kb or 0,
            self.COL_TYPE: lambda r: Path(r.path).suffix.lower(),
            self.COL_MTIME: lambda r: r.mtime or 0,
            self.COL_THUMB: lambda r: natural_key(Path(r.path).name),
            self.COL_LABEL: _color_key,
            self.COL_RATING: lambda r: _rating_for(r.path),
        }
        key = key_funcs.get(column, key_funcs[self.COL_NAME])
        reverse = order == Qt.SortOrder.DescendingOrder

        self.layoutAboutToBeChanged.emit()
        old_indexes = self.persistentIndexList()
        rows_before = self._rows[:]
        self._rows.sort(key=key, reverse=reverse)
        # Remap persistent indexes (selection / current) to their rows' new
        # positions — without this the layoutChanged contract leaves them mapped
        # to the old rows, so after a header sort the selection points at the
        # wrong image. Rows keep their identity, so track by object id.
        new_row_of = {id(r): i for i, r in enumerate(self._rows)}
        from_indexes, to_indexes = [], []
        for idx in old_indexes:
            if not idx.isValid() or not 0 <= idx.row() < len(rows_before):
                continue
            from_indexes.append(idx)
            to_indexes.append(self.index(new_row_of[id(rows_before[idx.row()])], idx.column()))
        self.changePersistentIndexList(from_indexes, to_indexes)
        self.layoutChanged.emit()
