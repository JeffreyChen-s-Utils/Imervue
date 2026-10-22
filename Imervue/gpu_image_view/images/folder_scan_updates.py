"""Merge scan chunks without rebuilding the entire viewer for every emitted batch."""
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


class FolderScanUpdates(QObject):
    """Show the first batch promptly, then coalesce updates until the final ordered list."""

    def __init__(self, apply: Callable[[list[str]], None], parent=None):
        super().__init__(parent if isinstance(parent, QObject) else None)
        self._apply = apply
        self._paths: list[str] = []
        self._seen: set[str] = set()
        self._active = True
        self._published = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush)

    def add(self, paths: list[str]) -> None:
        if not self._active:
            return
        for path in paths:
            if path not in self._seen:
                self._seen.add(path)
                self._paths.append(path)
        if not self._published:
            self._published = True
            self._flush()
        elif not self._timer.isActive():
            self._timer.start()

    def _flush(self) -> None:
        if self._active:
            self._apply(list(self._paths))

    def finish(self, paths: list[str]) -> None:
        if self._active:
            self._timer.stop()
            try:
                self._apply(list(paths))
            finally:
                self.cancel()

    def cancel(self) -> None:
        self._timer.stop()
        self._active = False
        self._apply = None
        self._paths.clear()
        self._seen.clear()
