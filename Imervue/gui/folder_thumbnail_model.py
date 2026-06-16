"""A QFileSystemModel that shows each folder's first image as its tree icon.

Windows' native shell folder thumbnails are fetched asynchronously by Qt and
appear only intermittently. This replaces them with app-generated, cached
previews — the folder's first image scaled to a small icon — produced on a
worker thread so the tree never blocks. Files keep their default icons; folders
with no readable image fall back to the default folder icon.

``folder_preview_path`` (which image to show) is pure and unit-tested; the model
is a thin cache + async-decode shell over it.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QFileSystemModel

logger = logging.getLogger("Imervue.gui.folder_thumbnail_model")

# QImage-decodable raster formats only — RAW/SVG need extra backends and would
# just yield a null preview, so we skip straight to the first one we can show.
PREVIEW_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
})
DEFAULT_ICON_SIZE = 32
MIN_ICON_SIZE = 16
MAX_ICON_SIZE = 128


def clamp_icon_size(px: int) -> int:
    """Clamp a requested thumbnail edge to the supported ``[16, 128]`` range."""
    return max(MIN_ICON_SIZE, min(MAX_ICON_SIZE, int(px)))


def folder_preview_path(folder: str, exts: Iterable[str] = PREVIEW_EXTS) -> str | None:
    """First (name-sorted) directly-contained image of *folder*, or None.

    Non-recursive; an unreadable / missing directory yields None rather than
    raising, so a transient permission error just means "no preview".
    """
    allowed = {e.lower() for e in exts}
    try:
        images = sorted(
            entry for entry in Path(folder).iterdir()
            if entry.is_file() and entry.suffix.lower() in allowed
        )
    except OSError:
        return None
    return str(images[0]) if images else None


class _PreviewSignals(QObject):
    done = Signal(str, QImage)   # folder, scaled thumbnail (null = no preview)


class _PreviewWorker(QRunnable):
    """Find a folder's first image and decode a scaled thumbnail off the UI thread."""

    def __init__(self, folder: str, exts: Iterable[str], size: int) -> None:
        super().__init__()
        self.signals = _PreviewSignals()
        self._folder = folder
        self._exts = exts
        self._size = size

    def run(self) -> None:
        thumb = QImage()
        path = folder_preview_path(self._folder, self._exts)
        if path is not None:
            image = QImage(path)
            if not image.isNull():
                thumb = image.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        self.signals.done.emit(self._folder, thumb)


class FolderThumbnailModel(QFileSystemModel):
    """File-system model whose folder icons are the folder's first image."""

    def __init__(self, parent=None, icon_size: int = DEFAULT_ICON_SIZE) -> None:
        super().__init__(parent)
        self._cache: dict[str, QIcon | None] = {}  # None = scanned, no preview
        self._pending: set[str] = set()
        self._pool = QThreadPool(self)
        self._icon_size = clamp_icon_size(icon_size)

    def icon_size(self) -> int:
        return self._icon_size

    def set_icon_size(self, px: int) -> None:
        """Set the preview edge size; drops the cache so previews re-decode
        crisply at the new size on the next paint."""
        px = clamp_icon_size(px)
        if px != self._icon_size:
            self._icon_size = px
            self._cache.clear()
            self._pending.clear()

    def data(self, index, role: int = Qt.ItemDataRole.DisplayRole):
        if (role == Qt.ItemDataRole.DecorationRole and index.column() == 0
                and self.isDir(index)):
            folder = self.filePath(index)
            if folder in self._cache:
                icon = self._cache[folder]
                if icon is not None:
                    return icon
            else:
                self._request_preview(folder)
        return super().data(index, role)

    def _request_preview(self, folder: str) -> None:
        if folder in self._cache or folder in self._pending:
            return
        self._pending.add(folder)
        worker = _PreviewWorker(folder, PREVIEW_EXTS, self._icon_size)
        worker.signals.done.connect(self._on_preview_ready)
        self._pool.start(worker)

    def _on_preview_ready(self, folder: str, thumb: QImage) -> None:
        self._pending.discard(folder)
        self._cache[folder] = None if thumb.isNull() else QIcon(QPixmap.fromImage(thumb))
        index = self.index(folder)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])
