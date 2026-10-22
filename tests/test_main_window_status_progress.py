"""Completion feedback must not hide a subsequent scan or overwrite newer messages."""
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QProgressBar, QWidget

from Imervue.gui.main_window_status import MainWindowStatusMixin


class StatusHost(QWidget, MainWindowStatusMixin):
    def __init__(self):
        super().__init__()
        self._status_label = QLabel(self)
        self._progress_bar = QProgressBar(self)
        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.setInterval(40)
        self._progress_hide_timer.timeout.connect(self._hide_progress)


@pytest.fixture
def host(qapp):
    widget = StatusHost()
    yield widget
    widget.deleteLater()


def test_new_scan_cancels_previous_completion_hide(host):
    host.show_progress(5, 5)
    host.show_progress(1, 10)
    QTest.qWait(80)
    assert not host._progress_bar.isHidden()
    assert host._progress_bar.value() == 1
    assert "1/10" in host._status_label.text()
    host.show_progress(10, 10)
    QTest.qWait(80)
    assert host._progress_bar.isHidden()


def test_new_message_survives_previous_completion_timer(host):
    host.show_progress(1, 1)
    host.set_status("Cannot read image")
    QTest.qWait(80)
    assert host._status_label.text() == "Cannot read image"
    assert host._progress_bar.isHidden()


def test_unknown_total_stays_busy_until_real_completion(host):
    host.show_progress(0, 0)
    QTest.qWait(80)
    assert not host._progress_bar.isHidden()
    assert not host._progress_hide_timer.isActive()
