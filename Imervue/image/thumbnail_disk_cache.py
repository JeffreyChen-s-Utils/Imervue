"""
縮圖磁碟快取
Persistent thumbnail disk cache — avoids re-decoding images on every folder open.
Uses .npy format for fast I/O (raw numpy array, no encode/decode overhead).
Cache key = md5(absolute_path | mtime_ns | file_size | thumbnail_size).
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.thumbnail_cache")


def _get_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "cache" / "thumbnails"
    return Path.home() / ".cache" / "imervue" / "thumbnails"


class ThumbnailDiskCache:

    def __init__(self):
        self._dir = _get_cache_dir()
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create cache dir {self._dir}: {e}")

    # --------------------------------------------------

    @staticmethod
    def _key(path: str, size: int) -> str:
        try:
            st = Path(path).stat()
            raw = f"{path}|{st.st_mtime_ns}|{st.st_size}|{size}"
        except OSError:
            return ""
        return hashlib.md5(raw.encode()).hexdigest()

    # --------------------------------------------------

    def get(self, path: str, size: int) -> np.ndarray | None:
        """嘗試從磁碟讀取快取的縮圖，失效或不存在時回傳 None"""
        key = self._key(path, size)
        if not key:
            return None
        cache_file = self._dir / f"{key}.npy"
        if cache_file.exists():
            try:
                return np.load(cache_file)
            except Exception:
                cache_file.unlink(missing_ok=True)
        return None

    def put(self, path: str, size: int, img_data: np.ndarray) -> None:
        """將縮圖寫入磁碟快取"""
        key = self._key(path, size)
        if not key:
            return
        cache_file = self._dir / f"{key}.npy"
        try:
            np.save(cache_file, img_data)
        except Exception as e:
            logger.debug(f"Failed to write thumbnail cache: {e}")


# 模組層級單例
thumbnail_disk_cache = ThumbnailDiskCache()
