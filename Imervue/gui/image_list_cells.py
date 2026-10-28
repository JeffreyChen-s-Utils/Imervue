"""Map Qt item roles to row presentation."""

from __future__ import annotations
from PySide6.QtCore import (
    QModelIndex,
    Qt,
)
from PySide6.QtGui import QColor
from Imervue.multi_language.language_wrapper import language_wrapper


class ImageListCellsMixin:
    """Map Qt item roles to row presentation."""

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

    def _background_value(self, row, col: int):
        if row.missing:
            return QColor(90, 36, 36, 140)
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
        if role == Qt.ItemDataRole.DecorationRole and col == self.COL_THUMB:
            self._ensure_fetched(row)
            return row.icon
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_RES, self.COL_SIZE):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == self.COL_RATING:
                return int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            return None
        if role == Qt.ItemDataRole.UserRole:
            return row.path
        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background_value(row, col)
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(row, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            if row.missing:
                return language_wrapper.language_word_dict.get(
                    "missing_relocate_hint",
                    "This file is missing. Relocate it or remove it from the view.",
                )
            return row.path
        return None
