"""
重複圖片掃描
Duplicate scan worker — the QThread that hashes a folder's images (file MD5 for
exact matches, dHash for perceptual ones) and emits the duplicate groups.
"""
from __future__ import annotations

import hashlib
import logging
import os

from PIL import Image
from PySide6.QtCore import QThread, Signal

from Imervue.gui.duplicate_detection_clusters import (
    _build_clusters,
    _flatten_hash_map,
    _union,
)
from Imervue.image.formats import JPEG_EXTENSIONS
from Imervue.image.perceptual_hash import dhash as _dhash
from Imervue.image.perceptual_hash import hamming_distance as _hamming_distance
from Imervue.image.perceptual_hash import upright
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.system.image_listing import list_images

logger = logging.getLogger("Imervue.duplicate_detection")

_IMAGE_EXTS = frozenset({
    ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif", ".apng",
}) | JPEG_EXTENSIONS

_METHOD_EXACT = "exact"


class _ScanWorker(QThread):
    """Scans a folder for duplicate images."""
    progress = Signal(int, int, str)      # current, total, filename
    result_ready = Signal(list)           # list of groups: [(path, hash, size), ...]
    error = Signal(str)

    def __init__(
        self,
        folder: str,
        method: str,           # "exact" or "perceptual"
        threshold: int,        # hamming distance threshold for perceptual
        recursive: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._folder = folder
        self._method = method
        self._threshold = threshold
        self._recursive = recursive
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            paths = self._collect_paths()
            if not paths:
                self.result_ready.emit([])
                return

            hash_map = self._build_hash_map(paths)
            if self._abort:
                return

            if self._method == _METHOD_EXACT:
                groups = [g for g in hash_map.values() if len(g) > 1]
            else:
                groups = self._cluster_perceptual(hash_map)

            self.result_ready.emit(groups)
        except Exception as e:
            logger.exception("Duplicate scan failed")
            self.error.emit(str(e))

    def _build_hash_map(
        self, paths: list[str],
    ) -> dict[str, list[tuple[str, int]]]:
        total = len(paths)
        hash_map: dict[str, list[tuple[str, int]]] = {}
        for i, path in enumerate(paths):
            if self._abort:
                return hash_map
            self.progress.emit(i + 1, total, os.path.basename(path))
            entry = self._hash_one(path)
            if entry is not None:
                key, size = entry
                hash_map.setdefault(key, []).append((path, size))
        return hash_map

    def _hash_one(self, path: str) -> tuple[str, int] | None:
        try:
            size = os.path.getsize(path)
            key = (self._file_hash(path) if self._method == _METHOD_EXACT
                   else self._perceptual_hash(path))
            return key, size
        except IMAGE_READ_ERRORS:
            logger.debug("Skipping %s", path, exc_info=True)
            return None

    def _collect_paths(self) -> list[str]:
        """The folder's images in natural name order; a cancel ends a recursive walk early."""
        return list_images(self._folder, _IMAGE_EXTS, recursive=self._recursive,
                           should_stop=lambda: self._abort)

    @staticmethod
    def _file_hash(path: str) -> str:
        # MD5 used purely for de-duplication, not security.
        h = hashlib.md5(usedforsecurity=False)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _perceptual_hash(path: str) -> str:
        with Image.open(path) as img:
            return str(_dhash(upright(img)))

    def _cluster_perceptual(
        self,
        hash_map: dict[str, list[tuple[str, int]]],
    ) -> list[list[tuple[str, int]]]:
        """Cluster perceptual hashes by hamming distance."""
        entries = _flatten_hash_map(hash_map)
        parent = list(range(len(entries)))
        if not self._union_similar(entries, parent):
            return []
        return _build_clusters(entries, parent)

    def _union_similar(
        self,
        entries: list[tuple[int, str, int]],
        parent: list[int],
    ) -> bool:
        n = len(entries)
        for i in range(n):
            if self._abort:
                return False
            for j in range(i + 1, n):
                if _hamming_distance(entries[i][0], entries[j][0]) <= self._threshold:
                    _union(parent, i, j)
        return True
