"""Reload the picture deep zoom shows when another program rewrites its file.

An external editor saves either in place or by writing a copy and renaming it
over the original. A folder watcher sees neither as a change - the file list
stays the same - so the viewer kept showing the old pixels. The shown file's
size and modification time are therefore read every :data:`POLL_MS`; once they
have moved away from the version on screen and then held still for one poll
(the editor has finished writing), the picture is reloaded. A save of the
viewer's own that already reloaded the picture changes nothing it compares, so
it is not reloaded twice.

The file is read rather than handed to ``QFileSystemWatcher``: on Windows a
file Qt watches made another program's rename-over save fail with "access
denied" about once in ten saves (54 of 600 measured, none while unwatched),
which neither a folder watch nor ``os.stat`` ever did.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

from Imervue.gpu_image_view.tile_loader import file_signature

#: How often the shown file is measured; a save shows within two of these.
POLL_MS = 500


class ShownFileWatch(QObject):
    """Watch one picture's file and report when another program rewrote it."""

    def __init__(self, is_shown: Callable[[str], bool], on_rewritten: Callable[[str], None],
                 parent: QObject | None = None) -> None:
        """*is_shown(path)*: is *path* still on screen; *on_rewritten(path)*: reload it."""
        super().__init__(parent)
        self._is_shown = is_shown
        self._on_rewritten = on_rewritten
        self._path: str | None = None
        self._signature = None   # the file as it was loaded
        self._seen = None        # the file at the last poll
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._tick)

    @property
    def path(self) -> str | None:
        """The file being watched, or None."""
        return self._path

    @property
    def polling(self) -> bool:
        """Whether the file is being measured."""
        return self._poll.isActive()

    def follow(self, path: str | None) -> None:
        """Watch *path*, the picture now loading, instead of the previous one; None stops watching.

        Records the file's size and modification time as they are now: a
        later change is measured against this load. A file that isn't there
        is not watched.
        """
        self._path = path
        self._signature = self._seen = file_signature(path) if path else None
        if self._signature is None:
            self._poll.stop()
        else:
            self._poll.start()

    def _tick(self) -> None:
        path = self._path
        if path is None:
            return
        seen = file_signature(path)
        held_still = seen == self._seen
        self._seen = seen
        if held_still:
            self._check(seen)

    def _check(self, signature) -> None:
        """Reload when *signature* - the file now - differs from the loaded one."""
        path = self._path
        if path is None or signature is None or signature == self._signature:
            return   # removed (the folder refresh handles that) or not really changed
        if not self._is_shown(path):
            return
        self._signature = signature
        self._on_rewritten(path)
