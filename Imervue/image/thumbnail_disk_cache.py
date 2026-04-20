"""
縮圖磁碟快取
Persistent thumbnail disk cache — avoids re-decoding images on every folder open.

Format: PNG (lossless, RGBA). We used to persist raw ``.npy`` RGBA arrays, but
a 512×512 thumbnail is ~1 MB uncompressed — on large libraries the cache dir
ballooned past 10 GB. PNG with compress_level=1 typically gets 3–5× smaller
with negligible decode overhead (PIL's PNG fast path), and is a standard
format anyone can inspect if they peek into the cache folder.

Cache key = md5(absolute_path | mtime_ns | file_size | thumbnail_size | recipe_hash).

``recipe_hash`` is the Develop panel's non-destructive edit fingerprint
(empty string for untouched images). When it changes, the thumbnail
automatically falls out of cache and gets rebaked with the new recipe.

Legacy ``.npy`` files left over from older Imervue builds are deleted on
startup during ``_scan_existing()`` so they don't count against the quota.

LRU eviction
------------
Each file's ``st_mtime`` acts as its LRU timestamp. On read we bump the
in-memory timestamp (we don't touch the disk to avoid extra I/O per cache hit).
When a ``put()`` pushes the total above ``max_total_bytes`` we evict
oldest-first until we're back under ``EVICT_RATIO * max_total_bytes``, giving
us a low-water / high-water style GC so bursts of puts don't trigger eviction
on every call.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image
import contextlib

logger = logging.getLogger("Imervue.thumbnail_cache")

_CACHE_EXT = ".png"
_LEGACY_EXTS = (".npy",)  # formats we quietly clean up at startup


def _get_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "Imervue" / "cache" / "thumbnails"
    return Path.home() / ".cache" / "imervue" / "thumbnails"


class ThumbnailDiskCache:
    DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
    EVICT_RATIO = 0.8  # evict down to 80% of the limit after hitting it

    def __init__(self, max_total_bytes: int = DEFAULT_MAX_BYTES):
        self._dir = _get_cache_dir()
        self._max_bytes = max_total_bytes
        self._lock = threading.Lock()
        # name -> (size_bytes, lru_timestamp)
        self._files: dict[str, tuple[int, float]] = {}
        self._total_bytes = 0
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create cache dir {self._dir}: {e}")
        self._scan_existing()

    # --------------------------------------------------
    # Internal bookkeeping
    # --------------------------------------------------

    def _scan_existing(self) -> None:
        """Index current-format files and delete any legacy-format leftovers."""
        try:
            with os.scandir(self._dir) as it:
                for entry in it:
                    name = entry.name
                    if name.endswith(_LEGACY_EXTS):
                        # Old .npy thumbnails from before the PNG migration —
                        # their cache keys don't match the new format anyway, so
                        # drop them instead of letting them squat on disk.
                        with contextlib.suppress(OSError):
                            (self._dir / name).unlink(missing_ok=True)
                        continue
                    if not name.endswith(_CACHE_EXT):
                        continue
                    try:
                        st = entry.stat()
                    except OSError:
                        continue
                    self._files[name] = (st.st_size, st.st_mtime)
                    self._total_bytes += st.st_size
        except OSError:
            return
        # If the on-disk cache is already over the limit (e.g. limit was lowered
        # between runs), do an initial eviction pass.
        if self._total_bytes > self._max_bytes:
            with self._lock:
                self._evict_locked()

    def _evict_locked(self) -> None:
        """Evict oldest entries until total is below EVICT_RATIO * max_bytes.

        Caller must hold ``self._lock``.
        """
        target = int(self._max_bytes * self.EVICT_RATIO)
        if self._total_bytes <= target:
            return
        # Sort by lru_timestamp ascending — oldest first.
        items = sorted(self._files.items(), key=lambda kv: kv[1][1])
        for name, (size, _ts) in items:
            if self._total_bytes <= target:
                break
            try:
                (self._dir / name).unlink(missing_ok=True)
            except OSError as e:
                logger.debug(f"Failed to evict {name}: {e}")
                continue
            self._total_bytes -= size
            self._files.pop(name, None)

    @staticmethod
    def _key(path: str, size: int, recipe_hash: str = "") -> str:
        try:
            st = Path(path).stat()
            raw = f"{path}|{st.st_mtime_ns}|{st.st_size}|{size}|{recipe_hash}"
        except OSError:
            return ""
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def get(self, path: str, size: int, recipe_hash: str = "") -> np.ndarray | None:
        """嘗試從磁碟讀取快取的縮圖，失效或不存在時回傳 None"""
        key = self._key(path, size, recipe_hash)
        if not key:
            return None
        name = f"{key}{_CACHE_EXT}"
        cache_file = self._dir / name
        if not cache_file.exists():
            return None
        try:
            with Image.open(cache_file) as src:
                # PNG round-trip through PIL; ensure RGBA so callers get a
                # uniform 4-channel array regardless of how it was stored.
                img = src.convert("RGBA") if src.mode != "RGBA" else src
                arr = np.array(img)
        except Exception as e:
            logger.debug(f"Thumbnail cache read failed for {name}: {e}")
            with contextlib.suppress(OSError):
                cache_file.unlink(missing_ok=True)
            with self._lock:
                old = self._files.pop(name, None)
                if old is not None:
                    self._total_bytes -= old[0]
            return None
        # Bump in-memory LRU timestamp on hit. We deliberately don't touch disk
        # mtime here — the next session will re-scan from disk mtimes, which is
        # fine: at worst we lose some cache-warmth info across restarts.
        with self._lock:
            entry = self._files.get(name)
            if entry is not None:
                self._files[name] = (entry[0], time.time())
        return arr

    def put(self, path: str, size: int, img_data: np.ndarray, recipe_hash: str = "") -> None:
        """將縮圖寫入磁碟快取，必要時 evict 舊項目"""
        key = self._key(path, size, recipe_hash)
        if not key:
            return
        # Normalise to RGBA uint8 so PIL can always save as PNG without guessing.
        try:
            arr = img_data
            if arr.dtype != np.uint8:
                arr = arr.astype(np.uint8, copy=False)
            if arr.ndim == 2:
                img = Image.fromarray(arr, mode="L").convert("RGBA")
            elif arr.shape[2] == 3:
                img = Image.fromarray(arr, mode="RGB").convert("RGBA")
            else:
                img = Image.fromarray(arr, mode="RGBA")
        except Exception as e:
            shape = getattr(img_data, "shape", None)
            logger.debug(f"Thumbnail cache: cannot interpret array shape={shape}: {e}")
            return

        name = f"{key}{_CACHE_EXT}"
        cache_file = self._dir / name
        try:
            # compress_level=1 = fastest PNG compression. We optimise for write
            # speed because this is a warm cache — most hits will come from the
            # first few folder opens after launch.
            img.save(cache_file, format="PNG", compress_level=1)
            st = cache_file.stat()
        except Exception as e:
            logger.debug(f"Failed to write thumbnail cache: {e}")
            return
        with self._lock:
            old = self._files.get(name)
            if old is not None:
                self._total_bytes -= old[0]
            self._files[name] = (st.st_size, time.time())
            self._total_bytes += st.st_size
            if self._total_bytes > self._max_bytes:
                self._evict_locked()

    def total_bytes(self) -> int:
        """Current on-disk cache size in bytes (for diagnostics / settings UI)."""
        with self._lock:
            return self._total_bytes

    def clear(self) -> None:
        """Delete every cached thumbnail. Used by 'Clear cache' in the UI."""
        with self._lock:
            for name in self._files:
                with contextlib.suppress(OSError):
                    (self._dir / name).unlink(missing_ok=True)
            self._files.clear()
            self._total_bytes = 0


# 模組層級單例
thumbnail_disk_cache = ThumbnailDiskCache()
