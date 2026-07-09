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
# A folder whose candidate image fails to decode (likely mid-move/delete on the
# worker thread) is retried up to this many times before falling back to the
# default icon, so a transient read race can't permanently blank its preview.
MAX_PREVIEW_RETRIES = 2


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
    # folder, scaled thumbnail (null = no usable preview), had_candidate.
    # ``had_candidate`` distinguishes "this folder has no image at all" from
    # "an image was found but failed to decode" (a transient mid-delete read),
    # so the model can retry the latter instead of caching a permanent blank.
    done = Signal(str, QImage, bool)


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
        had_candidate = path is not None
        if path is not None:
            image = QImage(path)
            if not image.isNull():
                thumb = image.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        self.signals.done.emit(self._folder, thumb, had_candidate)


class FolderThumbnailModel(QFileSystemModel):
    """File-system model whose folder icons are the folder's first image."""

    def __init__(self, parent=None, icon_size: int = DEFAULT_ICON_SIZE) -> None:
        super().__init__(parent)
        self._cache: dict[str, QIcon | None] = {}  # None = scanned, no preview
        self._pending: set[str] = set()
        # folder -> transient decode-failure retry count (see MAX_PREVIEW_RETRIES)
        self._retry: dict[str, int] = {}
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
            self._retry.clear()

    def clear_missing_previews(self) -> None:
        """Drop cached "no preview" markers so preview-less folders re-scan.

        Called after an external change (watchdog / F5 refresh) so a folder
        whose preview briefly failed to decode — or that just gained its first
        image — gets a fresh attempt on the next paint. Folders that already
        have a decoded preview keep it, so there is no flicker and no
        re-decode storm for the common case.
        """
        self._cache = {
            folder: icon for folder, icon in self._cache.items() if icon is not None
        }
        self._retry.clear()

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

    def _on_preview_ready(self, folder: str, thumb: QImage,
                          had_candidate: bool) -> None:
        self._pending.discard(folder)
        if not thumb.isNull():
            self._cache[folder] = QIcon(QPixmap.fromImage(thumb))
            self._retry.pop(folder, None)
            self._emit_decoration_changed(folder)
            return
        if had_candidate and self._bump_retry(folder):
            # A candidate image existed but failed to decode — almost always
            # because it was mid-move/delete when the worker read it. Retry
            # instead of poisoning the cache with a permanent "no preview".
            self._request_preview(folder)
            return
        # Genuinely no image, or repeated decode failures → default folder icon.
        self._cache[folder] = None
        self._retry.pop(folder, None)
        self._emit_decoration_changed(folder)

    def _bump_retry(self, folder: str) -> bool:
        """Increment *folder*'s retry counter; True while still under the cap."""
        count = self._retry.get(folder, 0)
        if count >= MAX_PREVIEW_RETRIES:
            return False
        self._retry[folder] = count + 1
        return True

    def _emit_decoration_changed(self, folder: str) -> None:
        index = self.index(folder)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])
