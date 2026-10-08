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
background initialization during ``_scan_existing()`` so they don't count against the quota.

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

from Imervue.image.formats import RAW_EXTENSIONS
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.system.atomic_write import replace_atomically

logger = logging.getLogger("Imervue.thumbnail_cache")

_CACHE_EXT = ".png"
# Bump when the cached pixels change meaning, so older entries stop matching.
# 2: thumbnails are EXIF-upright. 3: embedded colour profiles are converted to sRGB.
# 4: 16-bit and float greyscale is scaled over its range (it was clipped almost white) and a
#    greyscale picture's grey profile is applied.
_KEY_VERSION = 4
# Camera RAW entries only, so the rest of the cache stays valid.
# 4: a portrait RAW's embedded preview is turned upright.
_RAW_KEY_VERSION = 4
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
        if max_total_bytes < 0:
            raise ValueError("Thumbnail cache quota must be nonnegative")
        self._dir = _get_cache_dir()
        self._max_bytes = max_total_bytes
        self._lock = threading.RLock()
        self._generation = 0
        self._dirty: set[str] = set()
        self._scan_done = threading.Event()
        self._scan_cancel = threading.Event()
        # name -> (size_bytes, lru_timestamp)
        self._files: dict[str, tuple[int, float]] = {}
        self._total_bytes = 0
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Cannot create cache dir {self._dir}: {e}")
        self._scan_thread = threading.Thread(target=self._scan_existing, daemon=True,
                                             name="Imervue thumbnail inventory")
        self._scan_thread.start()

    # --------------------------------------------------
    # Internal bookkeeping
    # --------------------------------------------------

    def _scan_existing(self) -> None:
        """Inventory off the startup thread; mutations win over stale scan observations."""
        generation = self._generation
        try:
            with os.scandir(self._dir) as entries:
                for number, entry in enumerate(entries):
                    if self._scan_cancel.is_set() or not self._index_entry(entry, generation):
                        break
                    if number % 256 == 0:
                        time.sleep(0)  # yield the GIL to startup/foreground consumers
            with self._lock:
                if generation == self._generation and self._total_bytes > self._max_bytes:
                    self._evict_locked()
        except OSError as exc:
            logger.debug("Thumbnail inventory unavailable: %s", exc)
        except Exception:
            logger.exception("Thumbnail inventory failed unexpectedly")
        finally:
            with self._lock:
                self._dirty.clear()
                self._scan_done.set()

    def _index_entry(self, entry, generation: int) -> bool:
        name = entry.name
        try:
            if not entry.is_file(follow_symlinks=False):
                return True
            if name.endswith(_LEGACY_EXTS):
                with self._lock:
                    if generation != self._generation:
                        return False
                    (self._dir / name).unlink(missing_ok=True)
                return True
            if not name.endswith(_CACHE_EXT):
                return True
            observed = entry.stat(follow_symlinks=False)
        except OSError as exc:
            logger.debug("Cannot inventory thumbnail %s: %s", name, exc)
            if not name.endswith(_LEGACY_EXTS):
                return True
            try:
                observed = entry.stat(follow_symlinks=False)
            except OSError as stat_exc:
                logger.debug("Cannot account locked legacy thumbnail %s: %s", name, stat_exc)
                return True
        with self._lock:
            if generation != self._generation:
                return False
            if name not in self._files and name not in self._dirty:
                self._record_size(name, observed.st_size, observed.st_mtime)
        return True

    def _record_size(self, name: str, file_size: int, stamp: float) -> None:
        old = self._files.get(name)
        if old is not None:
            self._total_bytes -= old[0]
        self._files[name] = (file_size, stamp)
        self._total_bytes += file_size

    def _changed(self, name: str) -> None:
        if not self._scan_done.is_set():
            self._dirty.add(name)

    def wait_ready(self, timeout: float | None = None) -> bool:
        """Wait for inventory termination (diagnostics/tests only, never startup/UI code)."""
        return self._scan_done.wait(timeout)

    def close(self) -> None:
        """Stop/join inventory for an explicit cache owner; never required on the GUI thread."""
        self._scan_cancel.set()
        self._scan_thread.join()

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
            self._changed(name)

    @staticmethod
    def _key(path: str, size: int, recipe_hash: str = "") -> str:
        try:
            st = Path(path).stat()
            is_raw = Path(path).suffix.lower() in RAW_EXTENSIONS
            version = _RAW_KEY_VERSION if is_raw else _KEY_VERSION
            raw = f"{version}|{path}|{st.st_mtime_ns}|{st.st_size}|{size}|{recipe_hash}"
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
        try:
            observed = cache_file.stat()
        except OSError:
            return None
        try:
            with Image.open(cache_file) as src:
                # PNG round-trip through PIL; ensure RGBA so callers get a
                # uniform 4-channel array regardless of how it was stored.
                img = src.convert("RGBA") if src.mode != "RGBA" else src
                arr = np.array(img)
        except IMAGE_READ_ERRORS as e:
            # A truncated / corrupt PNG surfaces as OSError; drop it and re-render.
            logger.debug(f"Thumbnail cache read failed for {name}: {e}")
            self._purge_corrupt(cache_file, name, observed)
            return None
        with self._lock:
            self._changed(name)
            entry = self._files.get(name)
            if entry is not None:
                self._files[name] = (entry[0], time.time())
            else:
                try:
                    file_size = cache_file.stat().st_size
                except OSError as exc:
                    logger.debug("Read thumbnail disappeared before accounting: %s", exc)
                else:
                    self._record_size(name, file_size, time.time())
        return arr

    def _purge_corrupt(self, path: Path, name: str, observed) -> None:
        with self._lock:
            try:
                current = path.stat()
            except OSError:
                current = None
            # A parallel atomic put may already have replaced the bad file with a valid image.
            if current is not None and (current.st_ino, current.st_size, current.st_mtime_ns) != (
                    observed.st_ino, observed.st_size, observed.st_mtime_ns):
                return
            self._changed(name)
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.debug("Cannot purge corrupt thumbnail %s: %s", name, exc)
                self._record_size(name, observed.st_size, time.time())
                return
            old = self._files.pop(name, None)
            if old is not None:
                self._total_bytes -= old[0]

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
            if arr.ndim != 2 and arr.shape[2] not in (3, 4):
                raise ValueError(f"{arr.shape[2]} channels")
            # Pillow infers L / RGB / RGBA from the shape; passing a ``mode`` that
            # differs from it is removed in Pillow 13.
            img = Image.fromarray(arr).convert("RGBA")
        except (AttributeError, IndexError, TypeError, ValueError) as e:
            # Not an image-shaped array (no dtype / ndim, too few dims, odd channels).
            shape = getattr(img_data, "shape", None)
            logger.debug(f"Thumbnail cache: cannot interpret array shape={shape}: {e}")
            return

        name = f"{key}{_CACHE_EXT}"
        cache_file = self._dir / name
        with self._lock:
            try:
                replace_atomically(cache_file, lambda stage: img.save(
                    stage, format="PNG", compress_level=1))
                st = cache_file.stat()
            except (OSError, ValueError) as exc:
                logger.debug("Failed to write thumbnail cache: %s", exc)
                return
            self._changed(name)
            self._record_size(name, st.st_size, time.time())
            if self._total_bytes > self._max_bytes:
                self._evict_locked()

    def total_bytes(self) -> int:
        """Accounted bytes; provisional until background inventory terminates."""
        with self._lock:
            return self._total_bytes

    def clear(self) -> None:
        """Clear managed files, including unscanned ones; invalidate stale inventory entries."""
        with self._lock:
            self._generation += 1
            self._scan_cancel.set()
            previous, previous_total = self._files, self._total_bytes
            self._files = {}
            self._total_bytes = 0
            try:
                with os.scandir(self._dir) as entries:
                    for entry in entries:
                        self._clear_entry(entry)
            except OSError as exc:
                self._files, self._total_bytes = previous, previous_total
                logger.debug("Cannot enumerate thumbnail cache for clear: %s", exc)

    def _clear_entry(self, entry) -> None:
        if not entry.name.endswith((_CACHE_EXT, *_LEGACY_EXTS)):
            return
        try:
            if not entry.is_file(follow_symlinks=False):
                return
            (self._dir / entry.name).unlink(missing_ok=True)
        except OSError as exc:
            logger.debug("Cannot clear thumbnail %s: %s", entry.name, exc)
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as stat_exc:
                logger.debug("Cannot account retained thumbnail %s: %s", entry.name, stat_exc)
            else:
                self._record_size(entry.name, st.st_size, st.st_mtime)


# 模組層級單例
thumbnail_disk_cache = ThumbnailDiskCache()
