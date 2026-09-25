"""Reload the picture deep zoom shows when another program rewrites its file.

An external editor saves either in place or by writing a copy and renaming it
over the original. A folder watcher sees neither as a change - the file list
stays the same - so the viewer kept showing the old pixels. A watcher on the
file itself sees both. The reload waits until the writes have stopped for
:data:`SETTLE_MS`, and only happens when the file's size or modification time
really moved, so a save of the viewer's own that already reloaded the picture
is not repeated.

Qt on Windows tells a changed file by its modification time alone, so a save
that keeps the old time (a tool preserving file dates) sends no signal: the
file is also measured again whenever Imervue comes back to the front, which
is when someone returning from the editor looks.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QFileSystemWatcher, QObject, Qt, QTimer

from Imervue.gpu_image_view.tile_loader import file_signature

#: Quiet time after the last write before the picture is reloaded.
SETTLE_MS = 500


class ShownFileWatch(QObject):
    """Watch one picture's file and report when another program rewrote it."""

    def __init__(self, is_shown: Callable[[str], bool], on_rewritten: Callable[[str], None],
                 parent: QObject | None = None) -> None:
        """*is_shown(path)*: is *path* still on screen; *on_rewritten(path)*: reload it."""
        super().__init__(parent)
        self._is_shown = is_shown
        self._on_rewritten = on_rewritten
        self._path: str | None = None
        self._signature = None
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._check)
        app = QCoreApplication.instance()
        if app is not None and hasattr(app, "applicationStateChanged"):
            app.applicationStateChanged.connect(self._on_application_state)

    @property
    def path(self) -> str | None:
        """The file being watched, or None."""
        return self._path

    def follow(self, path: str | None) -> None:
        """Watch *path*, the picture now loading, instead of the previous one; None stops watching.

        Records the file's size and modification time as they are now: a
        later change is measured against this load.
        """
        self._settle.stop()
        watched = self._watcher.files()
        if watched:
            self._watcher.removePaths(watched)
        self._path = path
        self._signature = file_signature(path) if path else None
        if self._signature is not None:
            self._watcher.addPath(path)

    def _on_file_changed(self, path: str) -> None:
        if path == self._path:
            self._settle.start()   # every write restarts the wait

    def _on_application_state(self, state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive and self._path is not None:
            self._settle.start()   # back from the editor: measure the file again

    def _check(self) -> None:
        path = self._path
        if path is None or not self._is_shown(path):
            return
        signature = file_signature(path)
        if signature is None or signature == self._signature:
            return   # removed (the folder refresh handles that) or not really changed
        if path not in self._watcher.files():
            self._watcher.addPath(path)
        self._signature = signature
        self._on_rewritten(path)
