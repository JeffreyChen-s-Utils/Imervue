"""Render formatted image metadata without starting eager reads."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from Imervue.multi_language.language_wrapper import language_wrapper

from Imervue.gui.image_list_values import _fmt_size, _format_rating, _rating_for


class ImageListDisplayMixin:
    """Render formatted image metadata without starting eager reads."""

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
            self.COL_NAME: self._name_value,
            self.COL_RES: self._resolution_value,
            self.COL_SIZE: self._size_value,
            self.COL_TYPE: lambda r: Path(r.path).suffix.lstrip(".").upper() or "",
            self.COL_MTIME: self._mtime_value,
        }
        handler = handlers.get(col)
        return handler(row) if handler else ""

    @staticmethod
    def _name_value(row) -> str:
        name = Path(row.path).name
        if row.missing:
            lang = language_wrapper.language_word_dict
            return f"{name}  [{lang.get('tile_missing', 'Missing')}]"
        return name
