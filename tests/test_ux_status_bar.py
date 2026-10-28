"""The main window exposes retained task results without opening a tools menu."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMainWindow, QToolButton

from Imervue.gui.background_jobs import JobRegistry
from Imervue.gui.main_window_layout import MainWindowLayoutMixin
from Imervue.system.job_state import JobState


class StatusWindow(MainWindowLayoutMixin, QMainWindow):
    def _hide_progress(self):
        self._progress_bar.hide()

    def _collect_memory_pressure(self):
        return {}

    def _on_memory_pressure_clear(self):
        pass


def test_main_status_bar_opens_retained_failures(qapp, monkeypatch):
    registry = JobRegistry(qapp)
    monkeypatch.setattr(qapp, "_imervue_jobs", registry, raising=False)
    failed = JobState(["recording.mp4"])
    failed.record("recording.mp4", error="Disk full")
    failed.finish()
    registry.add_completed("Recording", failed)
    window = StatusWindow()
    try:
        window._build_status_bar()
        window.show()
        indicator = window.findChild(QToolButton, "backgroundJobIndicator")
        assert indicator is not None, "The main status bar has no task-results entry point"
        assert indicator.isVisible()
        indicator.setFocus()
        QTest.keyClick(indicator, Qt.Key.Key_Space)
        dialog = window._background_jobs_dialog
        assert dialog.isVisible()
        assert dialog.tree.topLevelItem(0).text(0) == "Recording"
        dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
        assert "Disk full" in dialog.tree.topLevelItem(0).child(0).text(2)
        dialog.close()
    finally:
        window.close()
        window.deleteLater()
        registry.deleteLater()
