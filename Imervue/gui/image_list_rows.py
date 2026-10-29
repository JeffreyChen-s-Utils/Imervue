"""Cached image metadata and GUI-thread thumbnail conversion."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtGui import QIcon, QImage, QPixmap, QColor

from Imervue.gui.image_list_values import _THUMB_SIZE


@dataclass
class _RowMeta:
    path: str
    missing: bool = False
    size_kb: float | None = None
    width: int | None = None
    height: int | None = None
    mtime: float | None = None
    icon: QIcon | None = None
    fetched: bool = False


class ImageListRowsMixin:
    """Initialize and update cached row values."""

    def _row_for_path(self, path: str) -> _RowMeta:
        row = _RowMeta(path, missing=not Path(path).exists())
        if self._metadata_index is None:
            return row
        meta = self._metadata_index.peek(path)
        if meta is None:
            return row
        row.size_kb = meta.size / 1024 if meta.size else None
        row.width = meta.width
        row.height = meta.height
        row.mtime = meta.mtime_ns / 1_000_000_000 if meta.mtime_ns else None
        return row

    @staticmethod
    def _pixmap_from_image(img: QImage) -> QPixmap:
        """Build the thumbnail QPixmap on the GUI thread (QPixmap is a
        QPaintDevice, so it must not be created on the worker thread). A null
        image — the worker's failure marker — yields the dark placeholder."""
        if img.isNull():
            pm = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
            pm.fill(QColor(40, 40, 40))
            return pm
        return QPixmap.fromImage(img)

    @staticmethod
    def _apply_row_meta(
        row: _RowMeta, pm: QPixmap, w: int, h: int, size_kb: float, mtime: float, ok: bool
    ) -> None:
        row.missing = not ok and not Path(row.path).exists()
        row.width = w or None
        row.height = h or None
        row.size_kb = size_kb if ok else None
        row.mtime = mtime if ok else None
        row.icon = QIcon(pm)
        row.fetched = True
