"""Never save over a store file that could not be read without keeping a copy of it.

A store that fails to read its file (broken JSON, a file another program
holds for a moment) starts empty, and its next save would replace the file —
every rating, recipe or note in it — with that empty state. The owner of the
file notes the failed read on an :class:`UnreadableFileGuard`, and asks it
before each save; the first save copies the file aside as
``<name>.unreadable-<date>-<time>``, and while no copy can be made the file
is left alone.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path


class UnreadableFileGuard:
    """Tracks one store file that could not be read, and keeps a copy of it before a save."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._lock = threading.Lock()
        self._pending = False              # a copy still has to be kept before the next save
        self._path: Path | None = None

    @property
    def unreadable_path(self) -> Path | None:
        """The file whose read failed, if one did; kept after its copy is made."""
        return self._path

    def note_unreadable(self, path: str | Path) -> None:
        """Record that *path* exists but could not be read, so the next save keeps a copy first."""
        with self._lock:
            self._pending = True
            self._path = Path(path)
        self._logger.warning(
            "Could not read %s; starting without it. A copy of it is kept before "
            "it is saved over.", path)

    def clear_to_save(self, path: str | Path) -> bool:
        """Whether saving over *path* is safe now; copies an unreadable file aside first.

        True when no read failed, the file is gone, or the copy was made (once).
        False, with the error logged, while the copy can't be made.
        """
        target = Path(path)
        with self._lock:
            if not self._pending or not target.exists():
                return True
            backup = target.with_name(
                f"{target.name}.unreadable-{time.strftime('%Y%m%d-%H%M%S')}")
            try:
                shutil.copy2(target, backup)
            except OSError:
                self._logger.exception(
                    "Could not keep a copy of the unreadable %s; not saving over it", target)
                return False
            self._pending = False
        self._logger.warning("Kept the file Imervue could not read as %s", backup)
        return True
