"""Thread-safe byte admission for speculative viewer images, independent of VRAM."""
from __future__ import annotations

import logging
import threading
import weakref

import numpy as np

logger = logging.getLogger("Imervue.ram_budget")
MIB = 1024 * 1024
FALLBACK_BYTES = 2048 * MIB


def auxiliary_ram_limit() -> int:
    """Use 20% of physical RAM (256 MiB–8 GiB), with an optional-psutil fallback."""
    try:
        import psutil
    except ImportError:
        return FALLBACK_BYTES
    try:
        total = int(psutil.virtual_memory().total)
    except (psutil.Error, OSError) as exc:
        logger.debug("Cannot probe physical RAM: %s", exc)
        return FALLBACK_BYTES
    return min(8192 * MIB, max(256 * MIB, total // 5))


def image_bytes(image: object) -> int:
    """Count distinct owned NumPy buffers in a pyramid or image, including shared views once."""
    arrays = getattr(image, "levels", (image,))
    roots = {}
    for array in arrays:
        if not isinstance(array, np.ndarray):
            continue
        root = array
        while isinstance(root.base, np.ndarray):
            root = root.base
        roots[id(root)] = int(root.nbytes)
    return sum(roots.values())


def decode_reservation(path: str, recipe: object = None) -> int:
    """Probe headers on the worker, reserving decode/pyramid scratch rather than compressed bytes.

    Unknown formats receive a conservative 512 MiB reservation. RAW header
    parsing never unpacks sensor data. Nonidentity recipes need float scratch.
    This is admission accounting, not an allocator or a process-RSS guarantee.
    """
    from pathlib import Path
    from Imervue.image.dimensions import image_dimensions
    from Imervue.image.formats import RAW_EXTENSIONS
    dimensions = image_dimensions(path)
    if dimensions is None:
        return 512 * MIB
    width, height = dimensions
    per_pixel = 48 if Path(path).suffix.lower() in RAW_EXTENSIONS else 24
    if recipe is not None and not recipe.is_identity():
        per_pixel = max(per_pixel, 160)
    return max(MIB, width * height * per_pixel)


class RamBudget:
    """Own reservations and cache accounting under a process-wide, fair window quota.

    A cancelled worker keeps its ticket until it actually exits. Queued results
    remain reserved until UI delivery transfers the ticket into cached bytes.
    Explicit limits are isolated for tests; production instances share one cap.
    """

    _lock = threading.RLock()
    _windows: weakref.WeakSet = weakref.WeakSet()
    _process_limit: int | None = None

    def __init__(self, limit: int | None = None) -> None:
        self._limit = max(1, limit) if limit is not None else None
        self.cache: dict[object, int] = {}
        self.reservations: dict[object, int] = {}
        with self._lock:
            if limit is None:
                if RamBudget._process_limit is None:
                    RamBudget._process_limit = auxiliary_ram_limit()
                self._windows.add(self)

    @property
    def limit_bytes(self) -> int:
        """Current fair share; existing excess is drained, never silently reclassified."""
        with self._lock:
            if self._limit is not None:
                return self._limit
            return (self._process_limit or FALLBACK_BYTES) // max(1, len(self._windows))

    @property
    def used_bytes(self) -> int:
        """Actual cache bytes plus reservations (including retired workers)."""
        with self._lock:
            return sum(self.cache.values()) + sum(self.reservations.values())

    def _fits(self, delta: int) -> bool:
        if self.used_bytes + delta > self.limit_bytes:
            return False
        return (self._limit is not None
                or sum(window.used_bytes for window in self._windows) + delta
                <= (self._process_limit or FALLBACK_BYTES))

    def reserve(self, ticket: object, size: int) -> bool:
        """Admit or resize one ticket without waiting or exceeding either quota."""
        size = max(0, int(size))
        with self._lock:
            delta = size - self.reservations.get(ticket, 0)
            if delta > 0 and not self._fits(delta):
                return False
            self.reservations[ticket] = size
            return True

    def store(self, key: object, size: int, *, ticket: object = None) -> bool:
        """Atomically exchange a completed ticket for its actual cached array bytes."""
        size = max(0, int(size))
        with self._lock:
            delta = size - self.cache.get(key, 0) - self.reservations.get(ticket, 0)
            if delta > 0 and not self._fits(delta):
                return False
            self.reservations.pop(ticket, None)
            self.cache[key] = size
            return True

    def release(self, ticket: object) -> None:
        """Release a completed worker ticket; repeated release is harmless."""
        with self._lock:
            self.reservations.pop(ticket, None)

    def discard(self, key: object) -> None:
        """Release cache accounting when its pixels are removed."""
        with self._lock:
            self.cache.pop(key, None)
