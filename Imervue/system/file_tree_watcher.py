"""Recursive file-tree watcher that drives the left-pane QFileSystemModel.

Qt's ``QFileSystemModel`` only watches the directories it has *opened* and
relies on native filesystem notifications. Bulk external changes (rsync,
git checkout, ``rm -rf``, drag-and-drop from another app) often don't
propagate until the user clicks the tree. This module fills that gap with
a recursive ``watchdog.Observer`` running on a background thread; any
change inside the watched root emits a debounced Qt signal on the UI
thread which then asks the model to re-stat its root.

Design notes:

* Background thread → UI thread hand-off via ``Signal``. The handler runs
  in watchdog's poller thread; touching ``QFileSystemModel`` directly from
  there would crash Qt.
* Debounce window of 500 ms collapses bursts (e.g. ``git checkout`` of a
  thousand files) into a single refresh.
* ``stop()`` is idempotent and safe to call repeatedly during shutdown.
* Falls back to a no-op when ``watchdog`` is missing so the app still
  starts on a barebones install.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from PySide6.QtWidgets import QFileSystemModel

logger = logging.getLogger("Imervue.file_tree_watcher")

_DEBOUNCE_MS = 500


class _WatchdogHandler:
    """``FileSystemEventHandler`` that funnels changes to a Qt signal.

    Defined as a plain class instead of inheriting from
    ``FileSystemEventHandler`` at module top-level so the import is lazy —
    we only require ``watchdog`` when the watcher is actually started.
    """

    def __init__(self, signal_emitter):
        self._emit = signal_emitter

    def on_any_event(self, event):
        # We don't care about specifics — any change in the tree warrants
        # re-stat-ing the root. Filtering by path here would risk missing
        # an "atomic" rename pair that happens to land outside our filter.
        try:
            self._emit()
        except Exception:  # noqa: BLE001 — never let UI errors kill watcher
            logger.debug("watchdog signal emission failed", exc_info=True)


class FileTreeWatchdog(QObject):
    """Watches a directory tree and re-roots a ``QFileSystemModel`` on change.

    Usage::

        wd = FileTreeWatchdog(parent=main_window)
        wd.bind_model(file_system_model)
        wd.watch("/some/folder")    # later, after navigating
        wd.stop()                   # on app shutdown
    """

    _changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._observer = None
        self._watched_path: str = ""
        self._model: QFileSystemModel | None = None

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._do_refresh)

        # Cross-thread hand-off: watchdog thread emits → debounce on UI thread
        self._changed.connect(self._on_change)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bind_model(self, model: QFileSystemModel) -> None:
        """Attach the model that should be refreshed when the tree changes."""
        self._model = model

    def watch(self, root: str) -> bool:
        """Start watching ``root`` (recursively). Returns True on success.

        If a previous root was being watched it is stopped first. Calling
        with an empty / nonexistent path stops watching entirely.
        """
        self.stop()
        if not root or not Path(root).is_dir():
            return False
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.info("watchdog not installed — file-tree auto-refresh disabled")
            return False

        handler_callable = _WatchdogHandler(self._changed.emit)

        class _Adapter(FileSystemEventHandler):
            def on_any_event(self, event):  # noqa: D401 — Qt-style hook
                handler_callable.on_any_event(event)

        try:
            observer = Observer()
            observer.schedule(_Adapter(), root, recursive=True)
            observer.daemon = True
            observer.start()
        except (OSError, RuntimeError) as exc:
            logger.warning("watchdog Observer failed to start on %s: %s", root, exc)
            return False

        self._observer = observer
        self._watched_path = root
        return True

    def stop(self) -> None:
        """Stop the observer if running. Safe to call multiple times."""
        observer = self._observer
        self._observer = None
        self._watched_path = ""
        if observer is None:
            return
        try:
            observer.stop()
            # join() with a short timeout — daemonised so it can't hang shutdown
            observer.join(timeout=1.0)
        except (RuntimeError, OSError) as exc:
            logger.debug("watchdog stop raised: %s", exc)

    @property
    def watched_path(self) -> str:
        return self._watched_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_change(self) -> None:
        # Restart debounce timer — bursts collapse into one refresh.
        self._debounce.start()

    def _do_refresh(self) -> None:
        model = self._model
        if model is None or not self._watched_path:
            return
        # ``setRootPath("")`` forces Qt to drop its internal cache for the
        # directory; setting it back re-stats every visible row.
        try:
            model.setRootPath("")
            model.setRootPath(self._watched_path)
        except (OSError, RuntimeError) as exc:
            logger.debug("model refresh raised: %s", exc)
