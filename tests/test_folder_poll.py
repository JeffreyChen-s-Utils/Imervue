"""The open folder is polled, not watched, so Windows can still rename the folders above it."""
from __future__ import annotations

import os
from types import SimpleNamespace

from PySide6.QtCore import Qt

from Imervue.gui.main_window_folders import MainWindowFoldersMixin
from Imervue.system.folder_poll import FolderPoller, folder_signature


def _bump(folder, seconds=5):
    """Move the folder's modification time, as adding or removing a file does."""
    stat = os.stat(folder)
    os.utime(folder, ns=(stat.st_atime_ns, stat.st_mtime_ns + seconds * 1_000_000_000))


def _poller(qapp, folder=None):
    poller = FolderPoller(None, interval_ms=10)
    changes = []
    poller.directoryChanged.connect(changes.append)
    if folder is not None:
        poller.watch(str(folder))
    return poller, changes


def test_folder_signature_is_the_modification_time(tmp_path):
    assert folder_signature(str(tmp_path)) == os.stat(tmp_path).st_mtime_ns


def test_folder_signature_of_a_missing_folder_is_none(tmp_path):
    assert folder_signature(str(tmp_path / "gone")) is None


def test_a_new_file_is_reported(qapp, tmp_path):
    poller, changes = _poller(qapp, tmp_path)
    (tmp_path / "new.png").write_bytes(b"x")
    _bump(tmp_path)
    poller.poll()
    assert changes == [str(tmp_path)]
    poller.deleteLater()


def test_an_unchanged_folder_reports_nothing(qapp, tmp_path):
    poller, changes = _poller(qapp, tmp_path)
    poller.poll()
    poller.poll()
    assert changes == []
    poller.deleteLater()


def test_a_change_is_reported_once(qapp, tmp_path):
    poller, changes = _poller(qapp, tmp_path)
    _bump(tmp_path)
    poller.poll()
    poller.poll()
    assert len(changes) == 1
    poller.deleteLater()


def test_a_folder_that_disappears_is_reported(qapp, tmp_path):
    folder = tmp_path / "shown"
    folder.mkdir()
    poller, changes = _poller(qapp, folder)
    folder.rmdir()
    poller.poll()
    assert changes == [str(folder)]
    poller.deleteLater()


def test_the_timer_polls_by_itself(qapp, tmp_path, pump_until):
    poller, changes = _poller(qapp, tmp_path)
    _bump(tmp_path)
    assert pump_until(lambda: changes, timeout=5.0)
    poller.stop()
    poller.deleteLater()


def test_watching_nothing_stops_polling(qapp, tmp_path):
    poller, changes = _poller(qapp, tmp_path)
    assert poller.directories() == [str(tmp_path)]
    assert poller._timer.isActive()  # noqa: SLF001
    poller.watch("")
    assert poller.directories() == []
    assert not poller._timer.isActive()  # noqa: SLF001
    _bump(tmp_path)
    poller.poll()
    assert changes == []
    poller.deleteLater()


def test_the_folders_above_a_polled_folder_can_be_renamed(qapp, tmp_path):
    """The point of polling: a QFileSystemWatcher's handle made this rename fail on Windows."""
    shown = tmp_path / "parent" / "shown"
    shown.mkdir(parents=True)
    poller, changes = _poller(qapp, shown)
    (tmp_path / "parent").rename(tmp_path / "renamed")
    assert (tmp_path / "renamed" / "shown").is_dir()
    poller.poll()
    assert changes == [str(shown)]       # gone from where it was
    poller.deleteLater()


class _Window(MainWindowFoldersMixin):
    def __init__(self):
        self.polls = 0
        self.refreshes = 0
        self._folder_watcher = SimpleNamespace(poll=self._count_poll)
        self.tree = SimpleNamespace(refresh=self._count_refresh)

    def _count_poll(self):
        self.polls += 1

    def _count_refresh(self):
        self.refreshes += 1


def test_coming_back_to_the_front_checks_the_folder_and_refreshes_the_tree():
    window = _Window()
    window._on_application_state_changed(Qt.ApplicationState.ApplicationActive)  # noqa: SLF001
    assert (window.polls, window.refreshes) == (1, 1)


def test_going_to_the_background_does_nothing():
    window = _Window()
    for state in (Qt.ApplicationState.ApplicationInactive, Qt.ApplicationState.ApplicationHidden):
        window._on_application_state_changed(state)  # noqa: SLF001
    assert (window.polls, window.refreshes) == (0, 0)
