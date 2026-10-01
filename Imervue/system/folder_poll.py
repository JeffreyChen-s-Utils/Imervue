"""Notice changes to the open folder by polling its modification time, without holding it open.

On Windows a folder cannot be renamed or moved while any process holds a
handle to a folder inside it, and every change-notification API holds one
(``QFileSystemWatcher``, ``FindFirstChangeNotification``, watchdog). So the
folder shown in the grid is not watched: :class:`FolderPoller` reads its
modification time about once a second, which opens and closes the folder at
once, and reports a change when the time moves (a file added, removed or
renamed). New files therefore show within a second or two rather than at once.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QTimer, Signal

POLL_INTERVAL_MS = 1000


def folder_signature(path: str) -> int | None:
    """The folder's modification time in nanoseconds, or ``None`` when it is gone or unreadable."""
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None


class FolderPoller(QObject):
    """Polls one folder; ``directoryChanged(path)`` fires when its entries change or it disappears.

    The signal and :meth:`directories` match ``QFileSystemWatcher``'s, so the
    main window treats it as the watcher it replaces.
    """

    directoryChanged = Signal(str)  # noqa: N815  # QFileSystemWatcher's name, kept for its callers

    def __init__(self, parent: QObject | None = None, interval_ms: int = POLL_INTERVAL_MS) -> None:
        super().__init__(parent)
        self._folder = ""
        self._signature: int | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll)

    def watch(self, folder: str) -> None:
        """Poll *folder* from now on; an empty string stops polling."""
        self._folder = folder
        self._signature = folder_signature(folder) if folder else None
        if folder:
            self._timer.start()
        else:
            self._timer.stop()

    def directories(self) -> list[str]:
        """The polled folder as a one-element list, or an empty list."""
        return [self._folder] if self._folder else []

    def poll(self) -> None:
        """Check the folder now; emits ``directoryChanged`` when its modification time moved."""
        if not self._folder:
            return
        signature = folder_signature(self._folder)
        if signature == self._signature:
            return
        self._signature = signature
        self.directoryChanged.emit(self._folder)

    def stop(self) -> None:
        """Stop polling (on window close)."""
        self.watch("")
